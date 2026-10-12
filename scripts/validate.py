#!/usr/bin/env python3
r"""Static checks for the my-cv repository.

Run it before every commit:      python scripts/validate.py

It verifies that

  1. data/cv.yaml parses and has all required keys
  1b. structural lint of data/cv.yaml: unknown / duplicate / empty keys, a UTF-8
      BOM, tabs, CRLF, trailing whitespace, a '#' that YAML keeps as text inside
      a block scalar, characters generate.py cannot map, and entries whose date
      ranges overlap (a date parser reads that as a data error)
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
# Shared helpers: the schema the renderers understand, and a YAML walker
# --------------------------------------------------------------------------- #
# Every key scripts/generate.py reads. A key outside these sets is silently
# ignored by the renderers *and* fails the sync check in section 5, so it is
# worth reporting here - with a message that names the key, not the content.
ENTRY_KEYS = ("name", "role", "company", "dates", "description",
              "technologies_tools", "responsibilities", "achievements")
ENTRY_REQUIRED = ("name", "role", "company", "dates")
META_KEYS = ("name", "role", "location", "phone", "phone_link", "email",
             "linkedin_label", "linkedin_url", "site_url",
             "page_title", "description", "pdf_title", "pdf_keywords",
             "preview_image", "pdf_download_name", "noindex")
THEME_KEYS = tuple(generate.CSS_VARS.values())
FONT_KEYS = ("latex", "html", "html_fallback")
LAYOUT_KEYS = ("margin_x_cm", "margin_y_cm", "max_width_px", "web_base_font_px")
GROUP_KEYS = ("name", "items", "level")
CERT_KEYS = ("name", "issuer", "issued", "expires", "credential_id")
DATE_RE = re.compile(r"^(\d{2})/(\d{4})\s*[-–]\s*(\d{2})/(\d{4})$")
PRESENT_RE = re.compile(r"^(\d{2})/(\d{4})\s*[-–]\s*[Pp]resent$")

# Design tokens live in both files but in different formats - skip them.
SKIP_PREFIXES = ("theme", "fonts", "layout")


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


def strict_load(text: str) -> list[str]:
    """yaml.safe_load, but report duplicate mapping keys (PyYAML hides them).

    Returns lines like "12: name" - never the offending source line, because
    PyYAML error messages quote it and this log is public.
    """
    duplicates: list[str] = []

    class StrictLoader(yaml.SafeLoader):
        pass

    def construct_mapping(loader, node, deep=False):
        seen = set()
        for key_node, _value in node.value:
            key = loader.construct_object(key_node, deep=deep)
            try:
                duplicate = key in seen
            except TypeError:                      # unhashable key: ignore
                continue
            if duplicate:
                duplicates.append(f"line {key_node.start_mark.line + 1}: {key}")
            seen.add(key)
        return yaml.SafeLoader.construct_mapping(loader, node, deep=deep)

    StrictLoader.add_constructor(
        yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, construct_mapping)
    yaml.load(text, Loader=StrictLoader)
    return duplicates


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
    for key in generate.SECTION_ORDER:
        section = data["sections"].get(key)
        if not section:
            fail(f"data/cv.yaml: section '{key}' is missing or empty")
        elif not section.get("title"):
            fail(f"data/cv.yaml: section '{key}' has no title")

    for key in ("name", "role", "location", "phone", "email", "linkedin_url"):
        if not data["meta"].get(key):
            fail(f"data/cv.yaml: meta.{key} is empty")

    # ----------------------------------------------------------------------- #
    # 1b) structural lint: schema, required/unknown keys, file hygiene.
    # Content quality is the author's call - these checks only catch what would
    # break a build, a parser or a reviewer. No value is ever printed: messages
    # name key *paths* (schema) and fingerprints (content).
    # ----------------------------------------------------------------------- #
    raw = generate.DATA_FILE.read_bytes()
    text = raw.decode("utf-8")

    if raw.startswith(b"\xef\xbb\xbf"):
        fail("data/cv.yaml: file starts with a UTF-8 BOM - strip it "
             "(some YAML tools then read the first key as '\\ufeffmeta')")
    if not text.endswith("\n"):
        fail("data/cv.yaml: the file does not end with a newline "
             "(.editorconfig: insert_final_newline)")
    if "\t" in text:
        fail("data/cv.yaml: contains a TAB character - YAML forbids tabs for "
             "indentation (use spaces)")
    if "\r" in text:
        notes.append("data/cv.yaml uses CRLF line endings "
                     "(.editorconfig asks for LF - harmless, but worth aligning)")
    trailing = [i + 1 for i, line in enumerate(text.replace("\r\n", "\n").split("\n"))
                if line != line.rstrip()]
    if trailing:
        notes.append(f"data/cv.yaml: trailing whitespace on {len(trailing)} line(s)")

    for duplicate in strict_load(text):
        fail(f"data/cv.yaml: duplicate mapping key ({duplicate}) - the second "
             f"one silently wins, so remove one")

    def unknown_keys(where: str, mapping, allowed) -> None:
        if not isinstance(mapping, dict):
            fail(f"data/cv.yaml: {where} must be a mapping")
            return
        for key in mapping:
            if key not in allowed:
                fail(f"data/cv.yaml: unknown key '{key}' under {where} - "
                     f"generate.py renders {', '.join(allowed)}")

    def required_keys(where: str, mapping, required) -> None:
        if not isinstance(mapping, dict):
            return
        for key in required:
            if not str(mapping.get(key, "")).strip():
                fail(f"data/cv.yaml: {where}.{key} is missing or empty")

    sections = data["sections"]
    unknown_keys("<root>", data, ("meta", "theme", "fonts", "layout", "sections"))
    unknown_keys("meta", data["meta"], META_KEYS)
    unknown_keys("theme", data["theme"], THEME_KEYS)
    unknown_keys("fonts", data["fonts"], FONT_KEYS)
    unknown_keys("layout", data["layout"], LAYOUT_KEYS)
    unknown_keys("sections", sections, tuple(generate.SECTION_ORDER))
    required_keys("meta", data["meta"], ("name", "role", "email", "phone"))

    entries = sections.get("experience_projects", {}).get("entries") or []
    where = "sections.experience_projects.entries"
    for i, entry in enumerate(entries):
        path = f"{where}[{i}]"
        unknown_keys(path, entry, ENTRY_KEYS)
        required_keys(path, entry, ENTRY_REQUIRED)
        for key in ("responsibilities", "achievements"):
            if key in entry and not isinstance(entry[key], list):
                fail(f"data/cv.yaml: {path}.{key} must be a list of bullets")
        dates = str(entry.get("dates", "")).strip()
        if dates and not (DATE_RE.match(dates) or PRESENT_RE.match(dates)):
            notes.append(f"data/cv.yaml: {path}.dates is not "
                         f"'MM/YYYY - MM/YYYY' or 'MM/YYYY - Present'")

    # Two entries covering the same period confuse date parsers (Workday/Taleo
    # parse dates strictly) and read as a data error to a reviewer.
    spans = []
    for i, entry in enumerate(entries):
        dates = str(entry.get("dates", "")).strip()
        match = DATE_RE.match(dates) or PRESENT_RE.match(dates)
        if not match:
            continue
        start = int(match.group(2)) * 12 + int(match.group(1))
        closed = DATE_RE.match(dates)
        end = int(closed.group(4)) * 12 + int(closed.group(3)) if closed else None
        spans.append((start, end, i))
    for position, (a_start, a_end, a_index) in enumerate(spans):
        for b_start, b_end, b_index in spans[position + 1:]:
            a_last = a_end if a_end is not None else 10 ** 6
            b_last = b_end if b_end is not None else 10 ** 6
            if a_start <= b_last and b_start <= a_last:
                notes.append(f"data/cv.yaml: {where}[{a_index}] and [{b_index}] "
                             f"overlap in time - parsers read that as a data error")

    for i, group in enumerate(sections.get("skills", {}).get("groups") or []):
        unknown_keys(f"sections.skills.groups[{i}]", group, GROUP_KEYS)
        required_keys(f"sections.skills.groups[{i}]", group, ("name", "items"))
    for i, cert in enumerate(sections.get("certificates", {}).get("entries") or []):
        unknown_keys(f"sections.certificates.entries[{i}]", cert, CERT_KEYS)
        required_keys(f"sections.certificates.entries[{i}]", cert,
                      ("name", "issuer", "issued", "expires"))
    for i, edu in enumerate(sections.get("education", {}).get("entries") or []):
        unknown_keys(f"sections.education.entries[{i}]", edu,
                     ("school", "major", "dates"))
        required_keys(f"sections.education.entries[{i}]", edu, ("school", "major"))
    for i, lang in enumerate(sections.get("languages", {}).get("entries") or []):
        unknown_keys(f"sections.languages.entries[{i}]", lang, ("name", "score"))
        required_keys(f"sections.languages.entries[{i}]", lang, ("name", "score"))

    # A '#' inside a block scalar (`>-` / `|`) is TEXT for YAML, not a comment, so
    # it ends up printed on the page. Plain scalars drop comments - which is why
    # this only ever bites inside a description.
    for path, token in walk(data):
        if path.split(".")[0] in SKIP_PREFIXES:
            continue
        if "#" in token:
            fail(f"data/cv.yaml: {path} contains a '#' - YAML keeps that as text "
                 f"inside a block scalar (it would be printed); {fingerprint(token)}")

    # Characters generate.tex() cannot map may or may not exist in the PDF font:
    # report the codepoints (never the text) so the PDF can be eyeballed.
    unmapped: dict[str, int] = {}
    for path, token in walk(data):
        if path.split(".")[0] in SKIP_PREFIXES:
            continue
        for char in token:
            if ord(char) > 127 and char not in generate._TEX_UNICODE:
                key = f"U+{ord(char):04X}"
                unmapped[key] = unmapped.get(key, 0) + 1
    if unmapped:
        notes.append("data/cv.yaml: characters generate.py does not map to LaTeX "
                     f"- check they print in the PDF: {sorted(unmapped)}")


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


# Values that only exist in the web page / only in the PDF metadata.
WEB_ONLY = {"meta.site_url", "meta.page_title", "meta.description",
            "meta.preview_image", "meta.pdf_download_name"}
PDF_ONLY = {"meta.pdf_title", "meta.pdf_keywords"}
# (SKIP_PREFIXES - the design-token prefixes - is defined with the lint above.)

tex_all = normalise("\n".join(
    open(f, encoding="utf-8").read() for f in tex_files
))
html_path = os.path.join(ROOT, "web", "index.html")
html_all = ""
if os.path.isfile(html_path):
    html_all = normalise_html(open(html_path, encoding="utf-8").read())

checked = 0
for path, token in walk(data or {}):
    if path.split(".")[0] in SKIP_PREFIXES:
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
