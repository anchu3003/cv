#!/usr/bin/env python3
r"""Password-protect the compiled CV - real PDF encryption, not a JS overlay.

The generated file asks for the password when it is opened in any PDF reader
(Acrobat, Chrome, Preview, ...), so you can hand recruiters a PDF plus a short
code and nobody else can read it.

Usage
-----
    python scripts/protect_pdf.py --password "my-code"
    python scripts/protect_pdf.py --password "my-code" --in src/cv.pdf --out dist/cv-protected.pdf
    CV_PDF_PASSWORD=my-code python scripts/protect_pdf.py     # CI / script friendly

Backends (the first one available is used)
  1. qpdf     native binary:  qpdf --encrypt PW PW 256 ...
  2. pikepdf  pure-python:    pip install pikepdf

Printing stays allowed (recruiters often print); copying text out and modifying
the file are blocked unless you pass --allow-copy.
"""

from __future__ import annotations

import argparse
import os
import pathlib
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
DEFAULT_IN = ROOT / "dist" / "cv.pdf"


def protect_with_qpdf(src: pathlib.Path, dst: pathlib.Path, password: str,
                      allow_copy: bool) -> None:
    cmd = [
        "qpdf", "--encrypt", password, password, "256",
        "--print=full",
        f"--extract={'y' if allow_copy else 'n'}",
        "--modify=none", "--annotate=n", "--form=n",
        "--", str(src), str(dst),
    ]
    subprocess.run(cmd, check=True)


def protect_with_pikepdf(src: pathlib.Path, dst: pathlib.Path, password: str,
                         allow_copy: bool) -> None:
    try:
        import pikepdf
        from pikepdf import Encryption, Permissions
    except ImportError:  # pragma: no cover
        raise SystemExit(
            "Neither qpdf nor pikepdf is available.\n"
            "  install qpdf           (apt install qpdf / winget install qpdf)\n"
            "  or: python -m pip install pikepdf"
        )
    allow = Permissions(
        accessibility=True,
        extract=allow_copy,
        modify_annotation=False,
        modify_assembly=False,
        modify_form=False,
        modify_other=False,
        print_lowres=True,
        print_highres=True,
    )
    with pikepdf.open(str(src)) as pdf:
        pdf.save(str(dst), encryption=Encryption(owner=password, user=password,
                                                 R=6, allow=allow))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--in", dest="src", default=str(DEFAULT_IN),
                        help="input PDF (default: dist/cv.pdf)")
    parser.add_argument("--out", dest="dst", default=None,
                        help="output PDF (default: <input>-protected.pdf)")
    parser.add_argument("--password", default=os.environ.get("CV_PDF_PASSWORD"),
                        help="password / access code (or set CV_PDF_PASSWORD)")
    parser.add_argument("--allow-copy", action="store_true",
                        help="also allow text extraction (default: blocked)")
    parser.add_argument("--backend", choices=("auto", "qpdf", "pikepdf"),
                        default="auto")
    args = parser.parse_args(argv)

    if not args.password:
        parser.error("no password given: use --password or set CV_PDF_PASSWORD")

    src = pathlib.Path(args.src).resolve()
    if not src.is_file():
        sys.exit(f"input PDF not found: {src}\n"
                 "build it first (make pdf / .\\build.ps1) or pass --in")

    dst = pathlib.Path(args.dst).resolve() if args.dst else \
        src.with_name(src.stem + "-protected.pdf")
    dst.parent.mkdir(parents=True, exist_ok=True)

    backend = args.backend
    if backend == "auto":
        backend = "qpdf" if shutil.which("qpdf") else "pikepdf"

    print(f"encrypting {src.name} -> {dst.name}  (backend: {backend})")
    if backend == "qpdf":
        protect_with_qpdf(src, dst, args.password, args.allow_copy)
    else:
        protect_with_pikepdf(src, dst, args.password, args.allow_copy)

    print(f"OK - {dst} now requires the password to open "
          f"({'copying allowed' if args.allow_copy else 'copying blocked'})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
