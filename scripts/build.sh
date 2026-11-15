#!/usr/bin/env bash
# my-cv - local build script (Linux / macOS)
#
# Requires a TeX distribution providing 'xelatex' + 'latexmk'
#   Debian/Ubuntu   sudo apt install latexmk texlive-xetex texlive-latex-extra \
#                                    texlive-fonts-recommended texlive-fonts-extra
#   Fedora          sudo dnf install latexmk texlive-xetex texlive-scheme-medium
#   macOS           brew install --cask mactex-no-gui   (or: brew install tectonic)
# and Python 3 with PyYAML:  python3 -m pip install pyyaml
#
# Usage:
#   scripts/build.sh                          # content + PDF  -> dist/cv.pdf
#   scripts/build.sh --site                   # + _site/ (PDF embedded in the page)
#   scripts/build.sh --protected "the-code"   # + dist/cv-protected.pdf
#   scripts/build.sh --skip-generate          # reuse src/generated/*.tex as-is
#
# `make` wraps the same steps - see `make help`.

set -euo pipefail

usage() {
  cat <<'EOF'
Usage: scripts/build.sh [options]

  --site                   also assemble _site/ (PDF embedded, like CI)
  --protected <code>       also write dist/cv-protected.pdf, asking for <code>
  --data <file>            CV source to render (default: ../cv-private/ai/cv.yaml)
  --skip-generate          do not re-render src/generated/*.tex + web/index.html
  -h, --help               show this help
EOF
}

repo_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
cd "$repo_root"

site=0
skip_generate=0
protected=""
data_file=${CV_DATA:-../cv-private/ai/cv.yaml}

while [ $# -gt 0 ]; do
  case "$1" in
    --site) site=1 ;;
    --skip-generate) skip_generate=1 ;;
    --data)
      if [ $# -lt 2 ]; then
        echo "--data needs a path, e.g. --data ../cv-private/ai/cv.yaml" >&2
        exit 2
      fi
      data_file=$2
      shift
      ;;
    --data=*) data_file=${1#*=} ;;
    --protected)
      if [ $# -lt 2 ]; then
        echo "--protected needs a code, e.g. --protected \"the-code\"" >&2
        exit 2
      fi
      protected=$2
      shift
      ;;
    --protected=*) protected=${1#*=} ;;
    -h|--help) usage; exit 0 ;;
    *)
      printf 'unknown option: %s\n\n' "$1" >&2
      usage >&2
      exit 2
      ;;
  esac
  shift
done

python_bin=${PYTHON:-python3}
if ! command -v "$python_bin" >/dev/null 2>&1; then
  echo "python3 not found on PATH. Install Python 3, then: python3 -m pip install pyyaml" >&2
  exit 1
fi
if ! "$python_bin" -c 'import yaml' >/dev/null 2>&1; then
  echo "PyYAML is missing. Install it with: $python_bin -m pip install pyyaml" >&2
  exit 1
fi
if ! command -v latexmk >/dev/null 2>&1; then
  echo "latexmk not found on PATH. Install a TeX distribution (e.g. sudo apt install latexmk texlive-xetex)." >&2
  exit 1
fi

# 1) Content: the CV YAML -> src/generated/*.tex + web/index.html
if [ "$skip_generate" -eq 0 ]; then
  if [ ! -f "$data_file" ]; then
    echo "no CV source at: $data_file" >&2
    echo "the content lives in the private data repository, e.g. --data ../cv-private/ai/cv.yaml" >&2
    exit 1
  fi
  echo ">> generating LaTeX + HTML from $data_file"
  "$python_bin" scripts/generate.py --data "$data_file"
fi

# 2) PDF: compile inside src/ so that \input{...} resolves.
echo ">> compiling src/cv.tex with XeLaTeX"
(cd src && latexmk -xelatex -interaction=nonstopmode -halt-on-error cv.tex)
mkdir -p dist
cp -f src/cv.pdf dist/cv.pdf
echo "Built dist/cv.pdf"

# 3) Optional extras
# Assemble the page the way CI does: the PDF is embedded in it (no PDF URL of its
# own), so the last step of the build is that file plus style.css.
if [ "$site" -eq 1 ]; then
  rm -rf _site
  mkdir -p _site
  cp -R web/. _site/
  rm -f _site/index.html _site/cv.pdf
  "$python_bin" scripts/embed_pdf.py --in web/index.html --pdf dist/cv.pdf --out _site/index.html
  echo "Open _site/index.html - CI then encrypts it with StatiCrypt (CV_PDF_PASSWORD)"
fi
if [ -n "$protected" ]; then
  "$python_bin" scripts/protect_pdf.py --in dist/cv.pdf --password "$protected"
fi
