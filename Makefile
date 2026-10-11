# my-cv - build helpers
# Requires a TeX distribution (TeX Live / MiKTeX) providing xelatex + latexmk.
# The content itself lives in data/cv.yaml: `make gen` regenerates the LaTeX
# sections (src/generated/*.tex) and the web page (web/index.html) from it.
# NOTE: compilation runs INSIDE src/ so that \input{...} resolves.
# On Windows without GNU Make, use ./build.ps1 instead.
#
# The content is committed ENCRYPTED (data/cv.yaml.age, age): data/cv.yaml is
# gitignored, so you edit the clear file and run `make encrypt` before pushing.

SRC_DIR := src
MAIN    := cv.tex
PDF     := cv.pdf
OUT     := dist

# age key handling: `make decrypt` / `make encrypt`
AGE_KEY_FILE ?= $(HOME)/.age/cv-key.txt
AGE_RECIPIENT ?= $(shell grep -o 'age1[a-z0-9]*' $(AGE_KEY_FILE) | tail -1)

.PHONY: all gen check pdf preview site protected encrypt decrypt clean

all: pdf

gen:
	python scripts/generate.py

check:
	python scripts/validate.py
	python scripts/generate.py --check

pdf: gen
	cd $(SRC_DIR) && latexmk -xelatex -interaction=nonstopmode -halt-on-error $(MAIN)
	@mkdir -p $(OUT)
	cp $(SRC_DIR)/$(PDF) $(OUT)/$(PDF)
	@echo "Built $(OUT)/$(PDF)"

# Social preview image for the web page (needs: pip install pypdfium2)
preview: pdf
	python scripts/preview.py

# Assemble the page the way CI does (PDF embedded in it, so the PDF has no URL of
# its own):  _site/index.html + _site/style.css. CI then encrypts it with
# StatiCrypt + CV_PDF_PASSWORD; locally you can open _site/index.html directly.
site: pdf
	@mkdir -p _site
	cp -r web/. _site/
	rm -f _site/index.html _site/preview.png _site/cv.pdf
	python scripts/embed_pdf.py --in web/index.html --pdf $(OUT)/$(PDF) --out _site/index.html
	@echo "Open _site/index.html (CI adds the StatiCrypt step)"

# Optional separate copy that asks for a code when opened:
#   make protected PASSCODE="code for HR"
protected: pdf
	python scripts/protect_pdf.py --in $(OUT)/$(PDF) --password "$(PASSCODE)"

# Encrypted source:  make encrypt  (clear -> data/cv.yaml.age, commit this one)
encrypt:
	age -e -r $(AGE_RECIPIENT) -o data/cv.yaml.age data/cv.yaml
	@echo "Encrypted data/cv.yaml -> data/cv.yaml.age (key: $(AGE_KEY_FILE))"

# Recreate the clear file from the repo copy:  make decrypt
decrypt:
	age -d -i $(AGE_KEY_FILE) -o data/cv.yaml data/cv.yaml.age
	@echo "Decrypted data/cv.yaml.age -> data/cv.yaml"

clean:
	-cd $(SRC_DIR) && latexmk -C $(MAIN)
	-rm -rf $(OUT)

