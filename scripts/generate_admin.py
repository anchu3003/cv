#!/usr/bin/env python3
r"""Render templates/admin.html into web/admin.html.

    python scripts/generate_admin.py                 # -> web/admin.html
    python scripts/generate_admin.py --check         # exit 1 when it is stale

The admin page holds no CV content and no credentials: the application log and
the CV snapshots live in a PRIVATE repository and are fetched by the browser at
runtime with the user's own token. All this script does is fill in the two
constants the page needs - the data-repository slug and the snapshot directory.
"""

from __future__ import annotations

import argparse
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / "templates" / "admin.html"
DEFAULT_OUT = ROOT / "web" / "admin.html"
DEFAULT_DATA_REPO = "anchu3003/cv-private"
DEFAULT_HISTORY_DIR = "cv-history"


def render(data_repo: str, history_dir: str) -> str:
    template = TEMPLATE.read_text(encoding="utf-8")
    replacements = {
        "{{DATA_REPO}}": data_repo,
        "{{HISTORY_DIR}}": history_dir,
    }
    for token, value in replacements.items():
        if token not in template:
            sys.exit(f"templates/admin.html is missing the {token} placeholder")
        template = template.replace(token, value)
    return template


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Render the admin page.")
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--data-repo", default=DEFAULT_DATA_REPO,
                        help="owner/repo of the PRIVATE data repository")
    parser.add_argument("--history-dir", default=DEFAULT_HISTORY_DIR,
                        help="snapshot directory inside the data repository")
    parser.add_argument("--check", action="store_true",
                        help="do not write; exit 1 if the output is out of date")
    args = parser.parse_args(argv)

    html = render(args.data_repo, args.history_dir)
    out = pathlib.Path(args.out)
    if args.check:
        if not out.is_file() or out.read_bytes() != html.encode("utf-8"):
            print(f"out of date - run: python scripts/generate_admin.py ({out})")
            return 1
        print(f"up to date: {out}")
        return 0
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(html.encode("utf-8"))
    print(f"generated {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
