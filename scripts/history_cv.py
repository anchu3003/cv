#!/usr/bin/env python3
r"""Record built CV PDFs as plain snapshots in the PRIVATE data repository.

    python scripts/history_cv.py add --root ../cv-private/cv-history \
        --site ai --pdf build/ai/src/cv.pdf --version ai@1a2b3c4 --pages 3
    python scripts/history_cv.py prune --root ../cv-private/cv-history --keep 20
    python scripts/history_cv.py list  --root ../cv-private/cv-history

Why here and not next to the site: a PDF is not encrypted, so it cannot be
published - a static host serves every file to anyone who asks. The private
repository is the only place a readable snapshot can live, and the admin page
fetches `cv-history/index.json` (and the PDFs next to it) with the user's token.

Layout under --root:

    index.json                                  <- the list the admin page renders
    <site>/<date>-<site>-<short sha>.pdf        <- one file per build

The file name carries the commit of the *data* repository the PDF was rendered
from, so `git -C ../cv-private show <sha>` explains every snapshot.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import pathlib
import shutil
import sys

SCHEMA = 1
SITES = ("ai", "backend")


def short(version: str) -> str:
    """`ai@1a2b3c4` -> `1a2b3c4`: the part that goes into the file name."""
    return version.split("@", 1)[1] if "@" in version else version


def relative_file(site: str, date: str, version: str) -> str:
    return f"{site}/{date}-{site}-{short(version)}.pdf"


def read_index(root: pathlib.Path) -> list[dict]:
    path = root / "index.json"
    if not path.is_file():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        sys.exit(f"{path}: invalid JSON ({exc})")
    entries = payload.get("entries", [])
    return [entry for entry in entries if isinstance(entry, dict) and entry.get("file")]


def parse_file(path: pathlib.Path) -> dict:
    """Metadata that is recoverable from the path alone."""
    site = path.parent.name
    stem = path.stem                      # 2026-11-15-ai-c32239e
    date = stem[:10]
    prefix = f"{date}-{site}-"
    sha = stem[len(prefix):] if stem.startswith(prefix) else stem
    return {
        "site": site,
        "date": date,
        "version": f"{site}@{sha}",
        "file": f"{site}/{path.name}",
        "bytes": path.stat().st_size,
    }


def rebuild_index(root: pathlib.Path, known: dict[str, dict]) -> list[dict]:
    """Index every *.pdf on disk, keeping the metadata `add` recorded earlier.

    Regenerating from the files (instead of only appending) means a manual
    delete, a rename or a prune can never leave a dangling entry behind.
    """
    entries = []
    for path in sorted(root.glob("*/*.pdf")):
        meta = parse_file(path)
        cached = known.get(meta["file"], {})
        meta["pages"] = int(cached.get("pages") or 0)
        meta["sha256"] = cached.get("sha256") or ""
        entries.append(meta)
    entries.sort(key=lambda entry: (entry["date"], entry["site"], entry["file"]),
                 reverse=True)
    return entries


def write_index(root: pathlib.Path, entries: list[dict]) -> None:
    root.mkdir(parents=True, exist_ok=True)
    payload = {"schema": SCHEMA, "entries": entries}
    (root / "index.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")


def prune_dir(root: pathlib.Path, keep: int) -> int:
    """Keep the newest `keep` files per site; return how many were dropped."""
    dropped = 0
    for site in {path.parent.name for path in root.glob("*/*.pdf")}:
        files = sorted(root.glob(f"{site}/*.pdf"))
        stale = files[:-keep] if keep > 0 else files
        for old in stale:
            old.unlink()
            dropped += 1
            print(f"pruned {old.relative_to(root)}")
    for site_dir in root.iterdir():
        if site_dir.is_dir() and not any(site_dir.iterdir()):
            site_dir.rmdir()
    return dropped



def add(args) -> int:
    pdf = pathlib.Path(args.pdf)
    if not pdf.is_file():
        sys.exit(f"no such PDF: {pdf}")
    raw = pdf.read_bytes()
    if not raw.startswith(b"%PDF"):
        sys.exit(f"not a PDF: {pdf}")

    date = args.date or datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    root = pathlib.Path(args.root)
    rel = relative_file(args.site, date, args.version)
    target = root / rel
    target.parent.mkdir(parents=True, exist_ok=True)

    known = {entry["file"]: entry for entry in read_index(root)}
    if target.is_file() and not args.force:
        # One snapshot per data revision. The 6-hourly rebuild renders the same
        # revision again, and it must not commit the same PDF over and over.
        print(f"already recorded {rel} - nothing to do")
        return 0
    shutil.copyfile(pdf, target)
    print(f"recorded {pdf} -> {target} ({len(raw)} B)")

    known[rel] = {
        "site": args.site,
        "version": args.version,
        "date": date,
        "pages": args.pages,
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "file": rel,
    }
    entries = rebuild_index(root, known)
    write_index(root, entries)
    print(f"{root}/index.json: {len(entries)} snapshot(s)")
    return 0


def prune(args) -> int:
    root = pathlib.Path(args.root)
    if not root.is_dir():
        print(f"{root}: nothing to prune")
        return 0
    dropped = prune_dir(root, args.keep)
    entries = rebuild_index(root, {entry["file"]: entry for entry in read_index(root)})
    write_index(root, entries)
    print(f"{root}/index.json: {len(entries)} snapshot(s), pruned {dropped}")
    return 0


def show(args) -> int:
    root = pathlib.Path(args.root)
    entries = read_index(root)
    if not entries:
        print(f"{root}/index.json: no snapshots yet")
        return 0
    print(f"{'file':<44} {'pages':>5} {'size':>9}")
    for entry in entries:
        print(f"{entry['file']:<44} {entry.get('pages', 0):>5} "
              f"{entry.get('bytes', 0) / 1024:>8.1f}K")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Record CV PDFs in the data repository.")
    sub = parser.add_subparsers(dest="command", required=True)

    p_add = sub.add_parser("add", help="record one built PDF")
    p_add.add_argument("--site", required=True, choices=SITES)
    p_add.add_argument("--pdf", required=True)
    p_add.add_argument("--version", required=True,
                       help="site@<short commit>, e.g. ai@1a2b3c4")
    p_add.add_argument("--pages", type=int, default=0)
    p_add.add_argument("--force", action="store_true",
                       help="replace the snapshot if that revision is already recorded")
    p_add.add_argument("--date", default="", help="YYYY-MM-DD (default: UTC today)")
    p_add.add_argument("--root", required=True,
                       help="cv-history/ inside the data repository")
    p_add.set_defaults(func=add)

    p_prune = sub.add_parser("prune", help="keep the newest N snapshots per site")
    p_prune.add_argument("--root", required=True)
    p_prune.add_argument("--keep", type=int, default=20)
    p_prune.set_defaults(func=prune)

    p_list = sub.add_parser("list", help="show the recorded snapshots")
    p_list.add_argument("--root", required=True)
    p_list.set_defaults(func=show)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
