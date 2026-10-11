#!/usr/bin/env python3
r"""Fail if a published site directory still contains the CV in plain text.

Everything the workflow publishes is encrypted first: the PDF with
`scripts/protect_pdf.py` (AES-256) and web/index.html with StatiCrypt. This
script is the guard that proves the result is clean - it runs in CI right before
the Pages artifact is uploaded.

    python scripts/check_site.py _site              # CI (content fingerprinted)
    python scripts/check_site.py _site --show-text  # local debugging only

Exit code 0 = nothing of data/cv.yaml is readable, 1 = it leaked (build fails).
The leaked strings are only printed with --show-text, because this workflow runs
in a public repository: the raw log and the annotations are world-readable.
"""

from __future__ import annotations

import hashlib
import os
import pathlib
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import generate  # noqa: E402  (local module: scripts/generate.py)

# Design tokens are not content (and hex colours are legitimately public in
# style.css). Same list as scripts/validate.py.
SKIP_PREFIXES = ("theme", "fonts", "layout")
MIN_LENGTH = 20       # short strings ("Java Developer") are not distinctive enough
MAX_NEEDLES = 40
MAX_ANNOTATIONS = 5   # how many leaks to surface as GitHub check annotations
# StatiCrypt stamps its runtime into the page; without it the page is plain HTML.
ENCRYPTED_MARKER = b"staticrypt"
# An encrypted PDF must carry an /Encrypt dictionary in its trailer, whatever
# the text inside the (compressed) streams looks like.
PDF_ENCRYPTED_MARKER = b"/Encrypt"
# Always check the contact details, even though they are short.
PII_KEYS = ("email", "phone", "phone_link")


def walk(node, prefix: str = ""):
    """Yield (path, string) for every string in the loaded YAML."""
    if isinstance(node, dict):
        for key, value in node.items():
            yield from walk(value, f"{prefix}.{key}" if prefix else key)
    elif isinstance(node, list):
        for value in node:
            yield from walk(value, prefix)
    elif isinstance(node, str) and node:
        yield prefix, node


def build_needles(data: dict) -> list[str]:
    """Every string that must never be readable in the published site."""
    needles = {generate.clean(data["meta"][key]) for key in PII_KEYS
               if data["meta"].get(key)}
    candidates = []
    for path, value in walk(data):
        root = path.split(".")[0]
        if root in SKIP_PREFIXES or root == "meta":
            continue          # metadata (URLs, titles) is allowed to be public
        text = generate.clean(value)
        if len(text) >= MIN_LENGTH:
            candidates.append(text)
    candidates.sort(key=len, reverse=True)
    needles.update(candidates[:MAX_NEEDLES])
    return sorted(needle for needle in needles if needle)


def fingerprint(text: str) -> str:
    """Name a leaked string without printing it.

    The workflow runs in a PUBLIC repository, so the log and the check
    annotations are world-readable: printing the CV text would leak exactly what
    this script exists to protect.
    """
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:8]
    return f"len={len(text)} sha256={digest}"


def pdf_password_protected(path: pathlib.Path):
    """True/False when pikepdf is available, None when it is not installed."""
    try:
        import pikepdf
    except ImportError:  # pragma: no cover
        return None
    try:
        with pikepdf.open(str(path)):
            return False
    except pikepdf.PasswordError:
        return True
    except Exception as exc:  # damaged file, not a PDF, ...
        return f"error: {exc}"


def scan(site: pathlib.Path, needles: list[str], show_text: bool) -> list[str]:
    """Raw byte search: works for the encrypted PDF just as well as for HTML."""
    leaks = []
    for path in sorted(site.rglob("*")):
        if not path.is_file():
            continue
        blob = path.read_bytes()
        for needle in needles:
            if needle.encode("utf-8") in blob:
                detail = repr(needle) if show_text else fingerprint(needle)
                leaks.append(f"{path.relative_to(site)}: plain text ({detail})")
    return leaks


def escape_workflow_command(message: str) -> str:
    """GitHub escapes %, CR and LF inside ::error:: messages."""
    return (message.replace("%", "%25")
                   .replace("\r", "%0D")
                   .replace("\n", "%0A"))


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    show_text = "--show-text" in argv
    argv = [arg for arg in argv if arg != "--show-text"]
    if len(argv) != 1:
        sys.exit("usage: python scripts/check_site.py <published-directory> [--show-text]")

    site = pathlib.Path(argv[0])
    if not site.is_dir():
        sys.exit(f"not a directory: {site}")

    needles = build_needles(generate.load_data())
    problems = []

    index = site / "index.html"
    if not index.is_file():
        problems.append("index.html: missing")
    elif ENCRYPTED_MARKER not in index.read_bytes().lower():
        problems.append("index.html: not encrypted (StatiCrypt marker not found)")

    for pdf in sorted(site.rglob("*.pdf")):
        name = pdf.relative_to(site)
        if PDF_ENCRYPTED_MARKER not in pdf.read_bytes():
            problems.append(f"{name}: no /Encrypt dictionary - the PDF is readable")
            continue
        # Belt and braces: actually try to open it without a password.
        protected = pdf_password_protected(pdf)
        if protected is False:
            problems.append(f"{name}: opens without a password - the PDF is readable")
        elif isinstance(protected, str):
            problems.append(f"{name}: could not be verified ({protected})")

    problems += scan(site, needles, show_text)

    files = [p for p in site.rglob("*") if p.is_file()]
    if problems:
        print("FAILED: the site would publish the CV in the clear:")
        for problem in problems:
            print("  -", problem)
        if not show_text:
            print("    (content is fingerprinted on purpose - the CI log is public;")
            print("     run this script locally with --show-text to see the strings)")
        # Also surface them as check annotations (visible in the Actions UI
        # without downloading the raw log).
        for problem in problems[:MAX_ANNOTATIONS]:
            print(f"::error title=Plain-text CV in the published site::"
                  f"{escape_workflow_command(problem)}")
        if len(problems) > MAX_ANNOTATIONS:
            print(f"::error::{len(problems) - MAX_ANNOTATIONS} more problem(s) "
                  f"({len(files)} files scanned) - see the raw log")
        return 1

    print(f"OK: {site} is encrypted - {len(files)} files scanned, "
          f"{len(needles)} content strings checked, none readable")
    return 0


if __name__ == "__main__":
    sys.exit(main())
