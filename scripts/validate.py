#!/usr/bin/env python3
r"""Static checks for the my-cv repository.

Run it before every commit:      python scripts/validate.py

It verifies that

  1. data/cv.yaml parses and has all required keys
  2. src/generated/*.tex + web/index.html are exactly what generate.py produces
     (i.e. nobody hand-edited a generated file)      -> "single source" guard
  3. every \input target exists, braces balance, \begin/\end match
  4. cv.tex inputs every generated section (no orphan / forgotten section)
  5. every string in data/cv.yaml still appears in BOTH renderings (PDF + web)
  6. web/index.html is well-formed enough (tags balance, no leftover {{tokens}})
  7. the GitHub Actions workflows are valid YAML
  8. data/cv.yaml.age (the encrypted source the repository carries) decrypts to
     exactly data/cv.yaml                         -> "did you forget to encrypt?"

Failure messages never quote the content: this runs in a public repository, so a
leaked string would end up in a world-readable log (they show a fingerprint).
"""

from __future__ import annotations

import glob
import hashlib
import html as html_mod
import os
import re
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    import yaml
except ImportError:  # pragma: no cover
    sys.exit("PyYAML is required:  python -m pip install pyyaml")

import generate  # noqa: E402  (local module: scripts/generate.py)

ROOT = generate.ROOT
errors: list[str] = []
notes: list[str] = []


def fail(message: str) -> None:
    errors.append(message)


def fingerprint(text: str) -> str:
    """Name a string without printing it (CI logs of this repo are public)."""
    return f"len={len(text)} sha256={hashlib.sha256(text.encode('utf-8')).hexdigest()[:8]}"


# --------------------------------------------------------------------------- #
# 1) data/cv.yaml
# --------------------------------------------------------------------------- #
# A branch may carry no CV source at all (the public template): the content checks
# are then skipped and only the tooling is validated.
data = None
if os.path.isfile(generate.DATA_FILE):
    try:
        data = generate.load_data()
    except SystemExit as exc:  # pragma: no cover
        sys.exit(str(exc))
else:
    notes.append("no data/cv.yaml in this branch - running the tooling checks only")

if data:
    for key in ("summary", "experience", "skills", "projects", "education",
                "languages", "certificates"):
        section = data["sections"].get(key)
        if not section:
            fail(f"data/cv.yaml: section '{key}' is missing or empty")
        elif not section.get("title"):
            fail(f"data/cv.yaml: section '{key}' has no title")

    for key in ("name", "role", "location", "phone", "email", "linkedin_url"):
        if not data["meta"].get(key):
            fail(f"data/cv.yaml: meta.{key} is empty")


# --------------------------------------------------------------------------- #
# 2) generated files must match the source of truth
# --------------------------------------------------------------------------- #
expected = generate.build_outputs() if data else {}
for rel, content in expected.items():
    path = os.path.join(ROOT, rel)
    if not os.path.isfile(path):
        fail(f"{rel}: missing (run: python scripts/generate.py)")
    elif open(path, "rb").read() != content.encode("utf-8"):
        fail(f"{rel}: out of date (run: python scripts/generate.py)")


# --------------------------------------------------------------------------- #
# 3) LaTeX structural checks
# --------------------------------------------------------------------------- #
tex_files = [
    f for f in glob.glob(os.path.join(ROOT, "src", "**", "*.tex"), recursive=True)
    if not os.path.basename(f).startswith("_")
]

for tex in tex_files:
    text = open(tex, encoding="utf-8").read()
    base = os.path.dirname(tex)
    for match in re.finditer(r"\\input\{([^}]+)\}", text):
        target = match.group(1)
        if data is None and target.startswith("generated/"):
            # The renderings are produced by CI from a source this branch does
            # not carry (the public template): nothing to check here.
            continue
        if not (os.path.isfile(os.path.join(base, target + ".tex"))
                or os.path.isfile(os.path.join(base, target))):
            fail(f"{os.path.relpath(tex, ROOT)}: missing input target '{target}'")
    stripped = re.sub(r"(?<!\\)%.*", "", text)            # drop comments
    stripped = re.sub(r"\\\$|\\%|\\#|\\&", "", stripped)  # ignore escaped specials
    if stripped.count("{") != stripped.count("}"):
        fail(f"{os.path.relpath(tex, ROOT)}: unbalanced braces "
             f"{{={stripped.count('{')} }}={stripped.count('}')}")
    begins = sorted(re.findall(r"\\begin\{([^}]+)\}", stripped))
    ends = sorted(re.findall(r"\\end\{([^}]+)\}", stripped))
    if begins != ends:
        fail(f"{os.path.relpath(tex, ROOT)}: begin/end mismatch {begins} != {ends}")


# --------------------------------------------------------------------------- #
# 4) every generated section is actually included by cv.tex
# --------------------------------------------------------------------------- #
cv_tex = open(os.path.join(ROOT, "src", "cv.tex"), encoding="utf-8").read()
for rel in expected:
    if not rel.startswith("src/generated/"):
        continue
    stem = os.path.basename(rel)[:-4]                     # e.g. "experience"
    if f"generated/{stem}" not in cv_tex:
        fail(f"src/cv.tex does not \\input{{generated/{stem}}}")


# --------------------------------------------------------------------------- #
# 5) every value in data/cv.yaml appears in BOTH renderings
# --------------------------------------------------------------------------- #
def normalise(text: str) -> str:
    """Make LaTeX and HTML comparable: undo escapes, markup, dashes."""
    text = html_mod.unescape(text)
    text = re.sub(r"<[^>]+>", " ", text)                  # HTML tags
    text = re.sub(r"\\([%&#_${}])", r"\1", text)          # \% -> %
    text = re.sub(r"\\[a-zA-Z@]+\*?", " ", text)          # \commands
    text = text.replace("--", "-")
    text = re.sub(r"[{}\\]", " ", text)
    text = text.replace("\u2013", "-").replace("\u2014", "-")
    text = text.replace("\u00b7", " ")
    return " ".join(text.split()).lower()


def normalise_html(text: str) -> str:
    """Same, but keep link/meta values (they are stripped with the tags)."""
    attrs = " ".join(re.findall(r'(?:href|content|src|download)="([^"]*)"', text))
    return normalise(re.sub(r"<[^>]+>", " ", text) + " " + attrs)


def walk(node, prefix: str = ""):
    """Yield (path, string) for every string in the loaded YAML."""
    if isinstance(node, dict):
        for key, value in node.items():
            yield from walk(value, f"{prefix}.{key}" if prefix else key)
    elif isinstance(node, list):
        for value in node:
            yield from walk(value, prefix)
    elif isinstance(node, str):
        if node:
            yield prefix, node


# Values that only exist in the web page / only in the PDF metadata.
WEB_ONLY = {"meta.site_url", "meta.page_title", "meta.description",
            "meta.preview_image", "meta.pdf_download_name"}
PDF_ONLY = {"meta.pdf_title", "meta.pdf_keywords"}
# Keys nothing renders any more: the PDF now travels *inside* the page (embedded
# by scripts/embed_pdf.py) instead of being linked, so a leftover `meta.pdf_url`
# in an older data/cv.yaml is skipped instead of reported as a sync error.
NOT_RENDERED = {"meta.pdf_url"}
# Design tokens live in both files but in different formats - skip them.
SKIP_PREFIXES = ("theme", "fonts", "layout")

tex_all = normalise("\n".join(
    open(f, encoding="utf-8").read() for f in tex_files
))
html_path = os.path.join(ROOT, "web", "index.html")
html_all = ""
if os.path.isfile(html_path):
    html_all = normalise_html(open(html_path, encoding="utf-8").read())

checked = 0
for path, token in walk(data or {}):
    if path.split(".")[0] in SKIP_PREFIXES or path in NOT_RENDERED:
        continue
    needle = normalise(token)
    if not needle:
        continue
    checked += 1
    if path not in WEB_ONLY and needle not in tex_all:
        fail(f"sync: {path}: missing from the LaTeX sources ({fingerprint(token)})")
    if path not in PDF_ONLY and html_all and needle not in html_all:
        fail(f"sync: {path}: missing from web/index.html ({fingerprint(token)})")
notes.append(f"content strings cross-checked in both renderings: {checked}")


# --------------------------------------------------------------------------- #
# 6) web page sanity
# --------------------------------------------------------------------------- #
from html.parser import HTMLParser  # noqa: E402

VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input",
        "link", "meta", "source", "track", "wbr"}


class TagChecker(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack: list[str] = []
        self.problems: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag not in VOID:
            self.stack.append(tag)

    def handle_endtag(self, tag):
        if tag in VOID:
            return
        if not self.stack:
            self.problems.append(f"stray </{tag}>")
        elif self.stack[-1] == tag:
            self.stack.pop()
        elif tag in self.stack:
            while self.stack and self.stack[-1] != tag:
                self.problems.append(f"unclosed <{self.stack.pop()}>")
            self.stack.pop()
        else:
            self.problems.append(f"stray </{tag}>")


if os.path.isfile(html_path):
    raw_html = open(html_path, encoding="utf-8").read()
    checker = TagChecker()
    checker.feed(raw_html)
    for tag in checker.stack:
        checker.problems.append(f"unclosed <{tag}>")
    for problem in checker.problems:
        fail(f"web/index.html: {problem}")
    if "style.css" not in raw_html:
        fail("web/index.html does not reference style.css")
    leftover = re.findall(r"\{\{[A-Z_]+\}\}", raw_html)
    if leftover:
        fail(f"web/index.html: unreplaced template tokens {sorted(set(leftover))}")
elif data:
    fail("web/index.html is missing")

for asset in ("web/style.css", "templates/index.html"):
    if not os.path.isfile(os.path.join(ROOT, asset)):
        fail(f"{asset} is missing")


# --------------------------------------------------------------------------- #
# 7) workflow YAML
# --------------------------------------------------------------------------- #
for wf in glob.glob(os.path.join(ROOT, ".github", "workflows", "*.yml")):
    try:
        with open(wf, encoding="utf-8") as handle:
            list(yaml.safe_load_all(handle))
        notes.append(f"YAML OK: {os.path.basename(wf)}")
    except Exception as exc:  # pragma: no cover
        fail(f"{wf}: invalid YAML ({exc})")


# --------------------------------------------------------------------------- #
# 8) the encrypted source must match the clear one (data/cv.yaml.age)
# --------------------------------------------------------------------------- #
AGE_FILE = os.path.join(ROOT, "data", "cv.yaml.age")
CLEAR_FILE = os.path.join(ROOT, "data", "cv.yaml")
age_key_file = os.environ.get("CV_AGE_KEY_FILE") or \
    os.path.join(os.path.expanduser("~"), ".age", "cv-key.txt")
age_bin = shutil.which("age")

if not os.path.isfile(AGE_FILE):
    notes.append("no data/cv.yaml.age in this branch - "
                 "nothing to compare with the clear source")
elif not os.path.isfile(CLEAR_FILE):
    notes.append("encrypted source present, clear file not decrypted here - "
                 "skipped the drift check")
elif not age_bin:
    notes.append("age not on PATH - skipped the encrypted-source drift check")
elif not os.path.isfile(age_key_file):
    notes.append(f"age key not found ({age_key_file}) - skipped the drift check")
else:
    decrypted = subprocess.run([age_bin, "-d", "-i", age_key_file, AGE_FILE],
                               capture_output=True)
    if decrypted.returncode != 0:
        detail = decrypted.stderr.decode("utf-8", "replace").strip()
        fail(f"age could not decrypt data/cv.yaml.age: {detail}")
    elif decrypted.stdout != open(CLEAR_FILE, "rb").read():
        fail("data/cv.yaml and data/cv.yaml.age differ - you edited the clear file "
             "without re-encrypting (run: make encrypt / scripts\\crypt.ps1 encrypt)")
    else:
        notes.append("encrypted source matches data/cv.yaml (age drift check)")


# --------------------------------------------------------------------------- #
# report
# --------------------------------------------------------------------------- #
notes.append(f"LaTeX files checked: {len(tex_files)}")
for note in notes:
    print("-", note)

if errors:
    print("FAILED:")
    for error in errors:
        print("  -", error)
    sys.exit(1)

print("ALL STATIC CHECKS PASSED")
