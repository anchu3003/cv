#!/usr/bin/env bash
# my-cv - one command to edit a CV whose source lives in the private data repo
#
# The CV text is NOT in this repository. It lives in ../cv-private (override with
# CV_DATA_REPO), one file per site:
#
#   ../cv-private/ai/cv.yaml        -> published at /cv/ai/
#   ../cv-private/backend/cv.yaml   -> published at /cv/backend/
#
# What this script does:
#
#   1. check that the source file exists
#   2. open it in $EDITOR and wait
#   3. regenerate  -> src/generated/*.tex + web/index.html   (this repo, gitignored)
#   4. validate    -> structure, schema, LaTeX/HTML sync
#   5. optionally commit + push **in the data repository**, then trigger the build
#
# Usage:
#   scripts/update.sh                          # edit (CV_SITE=ai) -> generate -> check
#   scripts/update.sh --site backend           # edit the backend CV instead
#   scripts/update.sh --push -m "content: ..." # commit + push in cv-private, then build
#   scripts/update.sh --no-edit                # no editor (CI, scripted runs)

set -euo pipefail

usage() {
  cat <<'EOF'
Usage: scripts/update.sh [options]

  --site <folder>      which CV to edit (a folder of the data repo; default ai)
  --data PATH          edit that file instead of ../cv-private/<site>/cv.yaml
  --no-edit            do not open $EDITOR (use the YAML as it is)
  --commit             commit the change in the DATA repository
  --push               commit and push in the DATA repository (implies --commit)
  -m, --message MSG    commit message (default: "content: update CV")
  -h, --help           show this help
EOF
}

repo_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
cd "$repo_root"

site=${CV_SITE:-ai}
data_file=""
edit=1
do_commit=0
do_push=0
message="content: update CV"

while [ $# -gt 0 ]; do
  case "$1" in
    --site) site=${2:-}; shift ;;
    --site=*) site=${1#*=} ;;
    --data) data_file=${2:-}; shift ;;
    --data=*) data_file=${1#*=} ;;
    --no-edit) edit=0 ;;
    --commit) do_commit=1 ;;
    --push) do_commit=1; do_push=1 ;;
    -m|--message)
      if [ $# -lt 2 ]; then
        echo "-m/--message needs a value, e.g. -m \"content: new role\"" >&2
        exit 2
      fi
      message=$2; shift ;;
    --message=*) message=${1#*=} ;;
    -h|--help) usage; exit 0 ;;
    *) printf 'unknown option: %s\n\n' "$1" >&2; usage >&2; exit 2 ;;
  esac
  shift
done

python_bin=${PYTHON:-python3}
command -v "$python_bin" >/dev/null 2>&1 || {
  echo "python3 not found on PATH. Install Python 3, then: python3 -m pip install pyyaml" >&2
  exit 1
}

data_repo=${CV_DATA_REPO:-../cv-private}
data_file=${data_file:-$data_repo/$site/cv.yaml}

if [ ! -f "$data_file" ]; then
  cat >&2 <<EOF
no CV source at: $data_file

The content lives in the private data repository. Clone it next to this one:
  git clone git@github.com:anchu3003/cv-private.git ../cv-private
(or point this script somewhere else:  --data /path/to/cv.yaml)
EOF
  exit 1
fi

# 1) edit -------------------------------------------------------------------- #
if [ "$edit" -eq 1 ]; then
  editor=${EDITOR:-${VISUAL:-vi}}
  echo ">> opening $data_file in $editor - save, quit, and the rest runs automatically"
  "$editor" "$data_file"
fi

# 2) render + validate in THIS repository ------------------------------------- #
echo ">> generating src/generated/*.tex + web/index.html from $data_file"
"$python_bin" scripts/generate.py --data "$data_file" > /dev/null

echo ">> validating (structure, schema, LaTeX/HTML sync)"
"$python_bin" scripts/validate.py --data "$data_file"
"$python_bin" scripts/generate.py --check --data "$data_file"

# 3) commit in the DATA repository -------------------------------------------- #
data_dir=$(cd -- "$(dirname -- "$data_file")/.." && pwd)
if ! git -C "$data_dir" rev-parse --git-dir >/dev/null 2>&1; then
  echo ">> $data_dir is not a git repository - skipping the commit/push step"
  exit 0
fi

if [ "$do_commit" -eq 0 ]; then
  echo
  echo "All checks passed. To publish:"
  echo "  git -C $data_dir commit -am \"$message\" && git -C $data_dir push"
  exit 0
fi

git -C "$data_dir" add -A
if git -C "$data_dir" diff --cached --quiet; then
  echo ">> nothing to commit in $data_dir"
else
  git -C "$data_dir" commit -m "$message"
fi

if [ "$do_push" -eq 0 ]; then
  echo "committed in $data_dir. Push when ready:  git -C $data_dir push"
  exit 0
fi

echo ">> pushing the data repository"
git -C "$data_dir" push
if command -v gh >/dev/null 2>&1; then
  echo ">> asking GitHub Actions to rebuild the site"
  gh workflow run build-cv.yml -R "${CV_SITE_REPO:-anchu3003/cv}" || \
    echo "   (could not trigger it - run: gh workflow run build-cv.yml -R anchu3003/cv)"
else
  echo "   trigger the build with: gh workflow run build-cv.yml -R anchu3003/cv"
fi
