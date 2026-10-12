#!/usr/bin/env python3
r"""Fault-injection tests for scripts/validate.py.

scripts/validate.py is the guard that keeps a broken data/cv.yaml out of the
build, so this file proves the guard actually fires: each case writes a
deliberately broken copy of data/cv.yaml into a scratch tree and checks that
validate.py reacts the way it should - a hard failure for a broken file, a note
(exit code stays 0) for a file that is merely suspect.

    python scripts/test_validate.py        # exit 0 = every case behaved
    python scripts/test_validate.py -v     # show validate.py output when one fails

The patches only touch schema keys (`name:`, `dates:`, `achievements:` …), so
this file never carries CV content - it is safe to keep in the public repo.
It needs data/cv.yaml plus the renderings generate.py writes, so on the content
branch it runs after the "Decrypt" and "Generate" steps (that is what the lint
workflow does). With no data/cv.yaml at all it reports that and exits 0.
"""

from __future__ import annotations

import argparse
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA_FILE = ROOT / "data" / "cv.yaml"
# The age drift check needs the identity key; this test is about the lint, so the
# check is pointed at a path that does not exist and validate.py skips it.
ENV = {**os.environ, "CV_AGE_KEY_FILE": str(ROOT / "no-such-key.txt")}
SKIP_DIRS = (".git", "_site", "dist", "__pycache__", ".vscode")


def run(*args: str, cwd: pathlib.Path):
    return subprocess.run([sys.executable, *args], cwd=cwd, env=ENV,
                          capture_output=True, text=True)


def replace_first(text: str, old: str, new: str) -> str:
    """Patch a fixture, failing loudly when the pattern moved."""
    if old not in text:
        raise AssertionError(f"test fixture pattern not found: {old!r}")
    return text.replace(old, new, 1)


def line_starting_with(text: str, prefix: str) -> str:
    for line in text.splitlines():
        if line.startswith(prefix):
            return line
    raise AssertionError(f"test fixture line not found: {prefix!r}")


def set_section_title(text: str, section_key: str, replacement: str) -> str:
    """Point one section's `title:` at `replacement` (line after `  <key>:`)."""
    lines = text.splitlines(keepends=True)
    for index, line in enumerate(lines):
        if line.rstrip("\r\n") == f"  {section_key}:":
            for offset in (1, 2):
                if lines[index + offset].startswith("    title:"):
                    lines[index + offset] = f"    title: {replacement}\n"
                    return "".join(lines)
    raise AssertionError(f"test fixture section not found: {section_key!r}")


def build_cases(good: str):
    """(name, expected exit code, needle, yaml text, regenerate) per case."""
    dates = [line for line in good.splitlines()
             if line.startswith("        dates:")]
    name_line = line_starting_with(good, "  name:")
    email_line = line_starting_with(good, "  email:")
    banner = line_starting_with(good, "# ---")
    if len(dates) < 2:
        raise AssertionError("test fixture wants two entries that carry dates")

    return [
        ("baseline: the real file passes end to end", 0,
         "ALL STATIC CHECKS PASSED", good, True),
        ("duplicate mapping key", 1, "duplicate mapping key",
         replace_first(good, name_line + "\n", name_line + "\n" + name_line + "\n"),
         False),
        ("unknown entry key", 1, "unknown key 'archivement'",
         replace_first(good, "        achievements:", "        archivement:"),
         False),
        ("unknown root key", 1, "unknown key 'extra_key'",
         good + "\nextra_key: 1\n", True),
        ("'#' kept as text inside a block scalar", 1, "contains a '#'",
         replace_first(good, "        description: >-\n",
                       "        description: >-\n          # note to self\n"),
         False),
        ("missing required entry key (dates)", 1, "dates is missing or empty",
         replace_first(good, dates[0] + "\n", ""), False),
        ("empty required meta value", 1, "meta.email is empty",
         replace_first(good, email_line + "\n",
                       email_line.split(":")[0] + ": ''\n"), False),
        ("tab character", 1, "TAB character",
         replace_first(good, banner, banner.replace("# ", "#\t", 1)), False),
        ("UTF-8 BOM", 1, "BOM", "\ufeff" + good, False),
        ("no newline at the end of the file", 1, "does not end with a newline",
         good.rstrip("\n"), False),
        ("responsibilities is not a list", 1, "must be a list of bullets",
         replace_first(good, "        responsibilities:\n",
                       "        responsibilities: >-\n"), False),
        ("entries whose date ranges overlap (note)", 0, "overlap in time",
         replace_first(good, dates[0] + "\n", dates[1] + "\n"), True),
        ("date format outside MM/YYYY (note)", 0, "dates is not",
         replace_first(good, dates[0] + "\n", "        dates: Q1 2026 - now\n"),
         True),
        ("section without a title", 1, "has no title",
         set_section_title(good, "certificates", "''"), True),
    ]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Fault-injection tests for scripts/validate.py")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="print validate.py output for every failing case")
    args = parser.parse_args(argv)

    if not DATA_FILE.is_file():
        print("no data/cv.yaml in this branch - nothing to test "
              "(tooling-only checkout): skipped")
        return 0

    cases = build_cases(DATA_FILE.read_text(encoding="utf-8"))
    failures = []

    with tempfile.TemporaryDirectory(prefix="cv-selftest-") as tmp:
        scratch = pathlib.Path(tmp) / "repo"
        shutil.copytree(ROOT, scratch, ignore=shutil.ignore_patterns(*SKIP_DIRS))
        target = scratch / "data" / "cv.yaml"

        for name, expected, needle, text, regenerate in cases:
            target.write_text(text, encoding="utf-8", newline="")
            if regenerate:
                run("scripts/generate.py", cwd=scratch)
            result = run("scripts/validate.py", cwd=scratch)
            output = result.stdout + result.stderr
            ok = result.returncode == expected and needle in output
            print(f"{'ok  ' if ok else 'FAIL'} {name}")
            if ok:
                continue
            failures.append(name)
            print(f"     exit code {result.returncode}, expected {expected}")
            print(f"     expected the output to contain: {needle}")
            if args.verbose:
                print("     ---- validate.py output ----")
                print("\n".join("     " + line for line in output.splitlines()))
            else:
                for line in output.splitlines():
                    if line.startswith(("  -", "FAILED")):
                        print("     got:", line[:160])
                        break

    if failures:
        print(f"\n{len(failures)} of {len(cases)} case(s) misbehaved: "
              f"{', '.join(failures)}")
        return 1
    print(f"\nall {len(cases)} cases behaved - validate.py still catches "
          f"a broken data/cv.yaml")
    return 0


if __name__ == "__main__":
    sys.exit(main())
