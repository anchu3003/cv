#!/usr/bin/env python3
r"""Render the site root chooser from the CV sources.

    python scripts/generate_chooser.py --data-dir ../cv-private \
        --out dist/index.html
    python scripts/generate_chooser.py --data-dir ../cv-private --check

One link per `<site>/cv.yaml` in the data directory:

    label = meta.site_label, else meta.role, else the folder name
    blurb = meta.site_summary (optional, one line under the label)

The page holds no CV content - a name, one line per CV, links - so it is safe to
publish in the clear. Adding a CV to the data repository is enough: the next
build lists it here.
"""

from __future__ import annotations

import argparse
import html
import pathlib
import sys

import yaml

MARKER = "Curricula Vitae"

PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<meta name="robots" content="noindex,nofollow"/>
<title>{title}</title>
<style>
 body{{margin:0;min-height:100vh;display:grid;place-items:center;background:#EEF1F5;color:#1A1A1A;font-family:Georgia,"Times New Roman",serif}}
 main{{max-width:34rem;padding:2rem;text-align:center}}
 h1{{font-size:1.6rem;margin:0 0 .25rem}}
 p{{color:#5A6472;margin:.25rem 0 1.5rem}}
 a{{display:block;margin:.6rem 0;padding:.85rem 1rem;border:1px solid #C9D6E4;border-radius:.5rem;background:#fff;color:#1F4E79;text-decoration:none}}
 a:hover{{border-color:#2E5C8A}}
 small{{display:block;color:#5A6472;font-weight:normal;margin-top:.2rem}}
 .admin{{margin-top:1.6rem}}
 .admin a{{display:inline-block;margin:0;padding:.45rem 1.05rem;font-size:.73rem;letter-spacing:.07em;
          text-transform:uppercase;border:1px solid #C9D6E4;border-radius:.5rem;background:#fff;
          color:#5A6472;font-family:-apple-system,"Segoe UI",Roboto,sans-serif;text-decoration:none}}
 .admin a:hover{{border-color:#2E5C8A;color:#1F4E79;background:#F2F6FB}}
</style></head>
<body><main>
 <h1>{name}</h1>
 <p>Choose a CV - each page asks for the same access code.</p>
{links}{admin}</main></body></html>
"""


def read_meta(path: pathlib.Path) -> dict:
    """`meta:` of one cv.yaml - the chooser needs nothing else, so the rest of
    the file is never parsed into anything that could leak."""
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        sys.exit(f"{path}: invalid YAML ({exc})")
    if not isinstance(data, dict):
        sys.exit(f"{path}: expected a mapping at the top level")
    return data.get("meta") or {}


def discover(data_dir: pathlib.Path) -> list[tuple[str, dict]]:
    """`[(site, meta), ...]`, ordered by folder name."""
    found = [(cv.parent.name, read_meta(cv)) for cv in sorted(data_dir.glob("*/cv.yaml"))]
    if not found:
        sys.exit(f"{data_dir}: no <site>/cv.yaml found")
    return found


def render(data_dir: pathlib.Path, admin_link: str | None = None) -> str:
    found = discover(data_dir)
    name = str(found[0][1].get("name") or MARKER)

    links = []
    for site, meta in found:
        label = str(meta.get("site_label") or meta.get("role") or site)
        blurb = str(meta.get("site_summary") or "").strip()
        caption = f"<small>{html.escape(blurb)}</small>" if blurb else ""
        links.append(f' <a href="{html.escape(site)}/">{html.escape(label)}{caption}</a>')

    admin = ""
    if admin_link:
        admin = f' <p class="admin"><a href="{html.escape(admin_link)}">admin</a></p>\n'

    return PAGE.format(title=html.escape(f"{name} - {MARKER}"),
                       name=html.escape(name),
                       links="\n".join(links) + "\n",
                       admin=admin)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Render the CV chooser page.")
    parser.add_argument("--data-dir", required=True,
                        help="repository carrying <site>/cv.yaml")
    parser.add_argument("--out", help="write the page here")
    parser.add_argument("--admin-link", default="",
                        help='add an admin button, e.g. "admin/" when /admin/ exists')
    parser.add_argument("--check", action="store_true",
                        help="do not write; exit 1 when --out is out of date")
    args = parser.parse_args(argv)

    page = render(pathlib.Path(args.data_dir), args.admin_link or None)
    if args.check:
        if not args.out:
            parser.error("--check needs --out")
        out = pathlib.Path(args.out)
        if not out.is_file() or out.read_text(encoding="utf-8") != page:
            print(f"out of date - run: python scripts/generate_chooser.py ({out})")
            return 1
        print(f"up to date: {out}")
        return 0
    if not args.out:
        parser.error("--out is required (or use --check)")
    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page, encoding="utf-8")
    print(f"generated {out} ({len(page)} B)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
