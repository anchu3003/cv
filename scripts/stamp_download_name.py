#!/usr/bin/env python3
r"""Expand the {date} token in the PDF download name.

    python scripts/stamp_download_name.py --in _site/index.html
    python scripts/stamp_download_name.py --in page.html --out page2.html \
        --date 2026-11-15

`meta.pdf_download_name` may carry `{date}`; it becomes DDMMYYYY (UTC today
unless --date is given), so HR sees e.g. `AnChu15112026SeniorAIEngineer.pdf`.

Why stamp at publish time instead of in generate.py: the generated page
(web/index.html) is committed, and baking today's date into it would make every
checkout stale tomorrow ("out of date" in `make check`). CI stamps the copy it is
about to encrypt, and `make site` stamps its preview.
"""

from __future__ import annotations

import argparse
import datetime
import pathlib
import sys

TOKEN = "{date}"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Expand {date} (DDMMYYYY) in the PDF download name.")
    parser.add_argument("--in", dest="src", required=True,
                        help="page to read")
    parser.add_argument("--out", help="write here (default: rewrite --in)")
    parser.add_argument("--date", default="",
                        help="YYYY-MM-DD (default: UTC today)")
    args = parser.parse_args(argv)

    when = (datetime.date.fromisoformat(args.date) if args.date
            else datetime.datetime.now(datetime.timezone.utc).date())
    src = pathlib.Path(args.src)
    out = pathlib.Path(args.out or args.src)
    text = src.read_text(encoding="utf-8")

    if TOKEN in text:
        text = text.replace(TOKEN, when.strftime("%d%m%Y"))
        print(f"stamped {out} with {when:%d%m%Y}")
    else:
        print(f"{out}: no {TOKEN} token - nothing to stamp")
    out.write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
