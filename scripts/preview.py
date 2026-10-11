#!/usr/bin/env python3
r"""Render the first page of the CV PDF to web/preview.png.

Used for the Open Graph / social preview image of the web page (and handy for
LinkedIn posts).  Optional step: it needs pypdfium2.

    python -m pip install pypdfium2
    python scripts/preview.py
"""

from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
PDF = ROOT / "src" / "cv.pdf"
OUT = ROOT / "web" / "preview.png"


def main() -> int:
    try:
        import pypdfium2 as pdfium
    except ImportError:  # pragma: no cover
        print("pypdfium2 is not installed - skipping preview generation")
        print("  python -m pip install pypdfium2")
        return 0

    if not PDF.is_file():
        print(f"{PDF} not found - build the PDF first (make pdf)")
        return 1

    document = pdfium.PdfDocument(str(PDF))
    page = document[0]
    scale = 1200 / page.get_width()          # ~1200 px wide preview
    image = page.render(scale=scale).to_pil()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    image.save(OUT, optimize=True)
    print(f"wrote {OUT.relative_to(ROOT)} ({image.width}x{image.height})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
