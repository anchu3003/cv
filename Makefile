# my-cv - build helpers (Linux / macOS)
#
# Requires a TeX distribution providing 'xelatex' + 'latexmk' and Python 3 with
# PyYAML. No other third-party module is needed.
#   Debian/Ubuntu:  sudo apt install latexmk texlive-xetex texlive-latex-extra \
#                                    texlive-fonts-recommended texlive-fonts-extra \
#                                    poppler-utils
#   (poppler-utils is only for `make pages`; without texlive-fonts-extra the
#    build still works but cvstyle.tex falls back to DejaVu Serif, so the PDF
#    will not look - or paginate - like the CI one.)
#   macOS:          brew install --cask mactex-no-gui && brew install poppler
#
# The CV content does NOT live in this repository: it is in the private data
# repository (default ../cv-private), and `make gen DATA=<file>` renders one of
# those files. This repository is the tooling + the published site.
# NOTE: compilation runs INSIDE src/ so that \input{...} resolves.
# Without GNU make, scripts/build.sh does the same thing.
#
# Run `make help` for the list of targets.

SRC_DIR := src
MAIN    := cv.tex
PDF     := cv.pdf
OUT     := dist

# `python` is not guaranteed to exist on a modern Linux box; override with
# `make pdf PYTHON=python` or an activated virtualenv if you need to.
PYTHON ?= python3

# Which CV to build locally. Point it at the private data repository, e.g.
#   make pdf DATA=../cv-private/ai/cv.yaml
#   make pdf DATA=../cv-private/backend/cv.yaml
CV_DATA ?= data/cv.yaml
DATA    ?= $(CV_DATA)
SITE    ?= ai
# Where the built PDFs get recorded (the PRIVATE repo's cv-history/).
HISTORY ?= ../cv-private/cv-history
VERSION ?= $(SITE)@$(shell git -C $(HISTORY)/.. rev-parse --short HEAD 2>/dev/null || echo local)

.DEFAULT_GOAL := all
.PHONY: all help update gen check pdf pages site protected admin history chooser clean

help:
	@echo "my-cv - make targets"
	@echo
	@echo "  make                 same as 'make pdf'"
	@echo "  make update          the whole edit cycle in one command (= scripts/update.sh)"
	@echo "                       --no-edit | --commit | --push | -m \"message\""
	@echo "  make gen             CV YAML -> src/generated/*.tex + web/index.html"
	@echo "  make check           validate.py + generate.py --check (before every commit)"
	@echo "  make pdf             generate + compile src/cv.tex -> dist/cv.pdf"
	@echo "  make pages           pdf + report the page count (PAGE_LIMIT=2 fails when longer)"
	@echo "  make site            pdf + _site/ (PDF embedded, exactly like CI)"
	@echo "  make protected PASSCODE=\"...\"   pdf + dist/cv-protected.pdf"
	@echo "  make admin           templates/admin.html -> web/admin.html (local preview)"
	@echo "  make history         copy dist/cv.pdf into $$HISTORY/<site>/ (private repo)"
	@echo "  make chooser         render the site chooser from the data repo (preview)"
	@echo "  make clean           remove the LaTeX aux files and dist/"
	@echo
	@echo "  DATA=<file>          CV to build (default: data/cv.yaml; usually"
	@echo "                       ../cv-private/<site>/cv.yaml)"
	@echo "  SITE=<folder>        which CV is being built (make history; default ai)"
	@echo "  HISTORY=<dir>        cv-history/ inside the data repo (make history)"

all: pdf

# The whole edit cycle in one command: decrypt -> edit -> generate -> encrypt ->
# validate. make cannot forward flags, so use scripts/update.sh --push (etc.)
# directly when you want the commit/push variants.
update:
	scripts/update.sh

gen:
	@test -f "$(DATA)" || { echo "no CV source at $(DATA) - pass DATA=<path> (e.g. DATA=../cv-private/ai/cv.yaml)"; exit 1; }
	$(PYTHON) scripts/generate.py --data $(DATA)

check:
	$(PYTHON) scripts/validate.py $(if $(wildcard $(DATA)),--data $(DATA),)
	@if [ -f "$(DATA)" ]; then $(PYTHON) scripts/generate.py --check --data $(DATA); fi

pdf: gen
	cd $(SRC_DIR) && latexmk -xelatex -interaction=nonstopmode -halt-on-error $(MAIN)
	@mkdir -p $(OUT)
	cp $(SRC_DIR)/$(PDF) $(OUT)/$(PDF)
	@echo "Built $(OUT)/$(PDF)"

# How long is the CV? Nothing in `validate.py` can answer that - only a real
# build can - so a side branch should run this instead of pushing and waiting
# for CI:   make pages                 -> "dist/cv.pdf: 3 page(s)"
#           make pages PAGE_LIMIT=2   -> exit 1 when the PDF is longer
PAGE_LIMIT ?=
pages: pdf
	@command -v pdfinfo >/dev/null 2>&1 || { \
	  echo "pdfinfo not found:  sudo apt install poppler-utils"; exit 1; }
	@pages=$$(pdfinfo $(OUT)/$(PDF) | awk '/^Pages:/ {print $$2}'); \
	echo "$(OUT)/$(PDF): $$pages page(s)"; \
	if [ -n "$(PAGE_LIMIT)" ] && [ "$$pages" -gt "$(PAGE_LIMIT)" ]; then \
	  echo "!! $$pages pages > PAGE_LIMIT=$(PAGE_LIMIT) - trim the CV before publishing"; \
	  exit 1; \
	fi

# Assemble the page the way CI does (PDF embedded in it, so the PDF has no URL of
# its own):  _site/index.html + _site/style.css. CI then encrypts it with
# StatiCrypt + CV_PDF_PASSWORD; locally you can open _site/index.html directly.
site: pdf
	@rm -rf _site
	@mkdir -p _site
	cp -R web/. _site/
	rm -f _site/index.html _site/cv.pdf
	$(PYTHON) scripts/embed_pdf.py --in web/index.html --pdf $(OUT)/$(PDF) --out _site/index.html
	@echo "Open _site/index.html (CI adds the StatiCrypt step)"

# Optional separate copy that asks for a code when opened:
#   make protected PASSCODE="code for HR"
protected: pdf
	$(PYTHON) scripts/protect_pdf.py --in $(OUT)/$(PDF) --password "$(PASSCODE)"

# Record a built PDF in the private repository's cv-history/. The file is plain,
# which is exactly why it lives there and not next to the site.
#   make history SITE=ai      (VERSION defaults to <site>@<data repo HEAD>)
history: pdf
	$(PYTHON) scripts/history_cv.py add --root $(HISTORY) --site $(SITE) \
	  --pdf $(OUT)/$(PDF) --version $(VERSION) \
	  --pages "$$(pdfinfo $(OUT)/$(PDF) 2>/dev/null | awk '/^Pages:/ {print $$2}' || echo 0)"
	@echo "now commit cv-history/ in the data repository with [skip dispatch]"

# Local preview of the admin page (no encryption, data comes from the browser).
admin:
	$(PYTHON) scripts/generate_admin.py
	@echo "open web/admin.html (CI encrypts it and publishes /admin/)"

# The site chooser, rendered from every <site>/cv.yaml in the data repository.
# CI writes this to _site/index.html; here it is just a preview.
chooser:
	$(PYTHON) scripts/generate_chooser.py --data-dir $(HISTORY)/.. --out $(OUT)/index.html
	@echo "open $(OUT)/index.html (CI publishes it at the site root)"

clean:
	-cd $(SRC_DIR) && latexmk -C $(MAIN)
	-rm -rf $(OUT)
