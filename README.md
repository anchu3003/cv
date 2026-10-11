# CV as Code

> One YAML file in — a consistent LaTeX PDF and a matching web page out, built and
> published by GitHub Actions, with **the source and both outputs encrypted** so a
> public repository can still hold a CV.

This repository is **tooling**: it contains no personal data. Your content lives in
`data/cv.yaml`, and the repository stores it **encrypted** (`data/cv.yaml.age`,
[age](https://age-encryption.org)) — so a fork starts empty, and nothing readable
is ever committed.

| You get | Built by | Published to |
| --- | --- | --- |
| `cv.pdf` (LaTeX / XeLaTeX) | GitHub Actions | GitHub Releases **and** Pages |
| `web/index.html` + `web/style.css` | GitHub Actions | GitHub Pages |

Both renderings are produced from the same source, so the palette, fonts and
margins can never drift apart. One code (`CV_PDF_PASSWORD`) optionally **encrypts
the PDF** (any reader asks for it) and **the web page** (StatiCrypt asks before
showing anything) — see [Keeping it private](#-keeping-it-private).

**Requirements**

| To do this | You need |
| --- | --- |
| Edit content | Python 3 + `python -m pip install pyyaml` |
| Build the PDF locally | TeX Live / MiKTeX with `xelatex` + `latexmk` — *or* skip it: CI compiles |
| Encrypt the source | [age](https://age-encryption.org): `winget install FiloSottile.age` · `apt install age` · `brew install age` |
| Run the pipeline | a GitHub repository with Actions + Pages (the free plan is enough) |

## 🚀 Use it for your CV

1. **Fork / clone / “Use this template”**, then:

   ```bash
   python -m pip install pyyaml
   cp data/cv.example.yaml data/cv.yaml        # PowerShell: Copy-Item
   ```

   `data/cv.example.yaml` is a complete, valid starter: the fields it shows are the
   required ones, everything else is optional. It passes
   `scripts/validate.py` as-is.

2. **Replace your details.** In `data/cv.yaml`, search for `YOUR-USER`, `YOUR-REPO`,
   `Your Name`, `Your Job Title` and `you@example.com` — that is every personal
   placeholder. Nothing in `scripts/`, `templates/` or the workflows is personal.

3. **Render and check**:

   ```bash
   python scripts/generate.py     # data/cv.yaml -> src/generated/*.tex + web/index.html
   python scripts/validate.py     # must print: ALL STATIC CHECKS PASSED
   ```

4. **Decide how private you want it** (details in
   [Keeping it private](#-keeping-it-private)):

   * **Encrypted source (default here)** — `age-keygen -o ~/.age/cv-key.txt`,
     `make encrypt` (Windows: `.\scripts\crypt.ps1 encrypt`), commit
     `data/cv.yaml.age`. The clear `data/cv.yaml` stays out of git (it is already
     in `.gitignore`).
   * **Plain source** — commit `data/cv.yaml` (delete it from `.gitignore`) and
     remove the encryption steps from `.github/workflows/build-cv.yml`. The
     workflow is deliberately *fail-closed*, so this is a change you make on
     purpose, not by forgetting a secret.
   * Only the first option keeps the repository safe to be public.

5. **Turn on the CI in your repository:**
   * **Settings → Secrets and variables → Actions**: add `AGE_KEY` (the content of
     your age identity file) and `CV_PDF_PASSWORD` (the code you hand out, 14+
     characters).
   * **Settings → Pages → Build and deployment → Source = `GitHub Actions`**.
   * **Settings → Actions → General → Workflow permissions = Read and write**.

6. **Push, then tag** to create the first Release:

   ```bash
   git add -A && git commit -m "my CV" && git push
   git tag v1 && git push origin v1
   ```

Your site is then at `https://YOUR-USER.github.io/YOUR-REPO/` and the permanent PDF
at `https://github.com/YOUR-USER/YOUR-REPO/releases/latest/download/cv.pdf`.
Optional badge for the top of your README:

```markdown
[![build](https://github.com/YOUR-USER/YOUR-REPO/actions/workflows/build-cv.yml/badge.svg)](https://github.com/YOUR-USER/YOUR-REPO/actions/workflows/build-cv.yml)
```

## 🔁 Updating your CV (the daily loop)

```bash
# 1. make sure the clear file is on disk (skip if you still have it)
make decrypt                       # Windows: .\scripts\crypt.ps1 decrypt

# 2. edit, then render and check
notepad data/cv.yaml
python scripts/generate.py
python scripts/validate.py         # also fails if the encrypted copy is out of date

# 3. re-encrypt and push (only the ciphertext is committed)
make encrypt                       # Windows: .\scripts\crypt.ps1 encrypt
git add -A && git commit -m "content: ..." && git push
```

On that push CI: decrypts `data/cv.yaml.age` (`AGE_KEY`) → regenerates the LaTeX and
the HTML → compiles the PDF → encrypts it (`CV_PDF_PASSWORD`) → encrypts the web
page with StatiCrypt → verifies that nothing readable survives → deploys to Pages.
A GitHub Release (and the permanent `releases/latest/download/cv.pdf` link) is
updated when you push a tag:

```bash
git tag v2 && git push origin v2
```

`scripts/validate.py` guards the most likely mistake: it decrypts
`data/cv.yaml.age` with your local key and compares it with `data/cv.yaml`, so a
forgotten `make encrypt` is caught locally instead of silently publishing the
previous version.

## 📁 Project structure

```
.
├─ data/
│  ├─ cv.yaml                  ★ your content, clear text (gitignored, never pushed)
│  ├─ cv.yaml.age              ★ the same content, encrypted — this is what the repo holds
│  └─ cv.example.yaml          a complete starter file to copy from
├─ src/
│  ├─ cv.tex                   entry point: section order (XeLaTeX)
│  ├─ cvstyle.tex              look & feel of the PDF (fonts, macros, spacing)
│  └─ generated/               ⟵ built from data/cv.yaml, never committed
├─ templates/
│  └─ index.html               shell of the web page (placeholders only)
├─ web/
│  ├─ index.html               ⟵ built from data/cv.yaml, never committed
│  ├─ style.css                look & feel of the web page (uses CSS variables)
│  └─ preview.png              local OG preview image (make preview, not published)
├─ scripts/
│  ├─ generate.py              data/cv.yaml -> LaTeX + HTML
│  ├─ validate.py              static checks + "did you forget to encrypt?"
│  ├─ crypt.ps1                encrypt / decrypt the source (Windows)
│  ├─ protect_pdf.py           AES-256 encrypt the PDF (needs CV_PDF_PASSWORD)
│  ├─ check_site.py            fails the build if _site still has plain text
│  └─ preview.py               first PDF page -> web/preview.png
├─ .github/workflows/
│  ├─ build-cv.yml             decrypt -> generate -> compile -> encrypt -> Release + Pages
│  └─ lint.yml                 decrypt -> generate + validate + spell check
├─ Makefile / build.ps1        local helpers (make encrypt / make decrypt)
└─ LICENSE
```

**Not committed** (all in `.gitignore`, they never reach GitHub): `data/cv.yaml`,
`src/generated/`, `web/index.html`, `web/preview.png`, `dist/`, `_site/`, any age
identity key, and local notes such as `Agent.md` or `.secrets`.

## 🔁 How the pipeline works

```
   data/cv.yaml.age   ← what the repository carries (age, ChaCha20-Poly1305)
             │  age -d -i $AGE_KEY        (CI)   /  make decrypt   (you)
             ▼
   data/cv.yaml       ← clear text: exists on the CI runner and on your machine only
             │
   scripts/generate.py
      ├──► src/generated/*.tex ── XeLaTeX ──► src/cv.pdf
      └──► web/index.html
                    │
        scripts/validate.py  → fails if a section is missing, if a value from
                               cv.yaml is not in BOTH renderings, or if the
                               encrypted copy is out of date
                    │
        ┌───────────┴────────────┐   encrypt with CV_PDF_PASSWORD
   protect_pdf.py          StatiCrypt (CI)
        │                        │
   dist/cv.pdf ────────► _site/cv.pdf + _site/index.html ──► GitHub Pages
        └───────────────────────────────────────────────────► Release
                    │
        scripts/check_site.py → fails if anything published still contains the CV
                                in clear text (every PDF must need a password)
```

Only ciphertext ever leaves the runner: the plaintext PDF is compiled there and
never uploaded, published or attached.

## ✍️ Editing the content (`data/cv.yaml`)

Everything is plain text — you never write LaTeX or HTML by hand; `%`, `&`, `_`,
quotes and dashes are escaped for you.

```yaml
meta:                     # name, role, contact details, page/PDF titles, links …
theme:                    # the palette used by BOTH renderings
fonts:                    # latex: a font shipped with TeX Live | html: a Google-Fonts family
layout:                   # PDF margins + the maximum width of the web page
sections:
  summary:      { title: Profile Summary, text: "…" }
  experience:   { title: Experience, entries: [ {role, company, dates, highlights?} ] }
  skills:       { title: Skills, groups: [ {name, items, level?} ] }
  projects:     { title: Projects, entries: [ {name, dates, description,
                                               responsibilities[], technologies} ] }
  education:    { title: Education, entries: [ {school, major, dates} ] }
  languages:    { title: Language, entries: [ {name, score} ] }
  certificates: { title: Certificates, entries: [ {name, issuer, issued,
                                                   expires, credential_id?} ] }
```

`sections` must contain all seven keys, and the order in which they are rendered is
fixed in `SECTION_ORDER` inside `scripts/generate.py` — not by the order in the
file. `data/cv.example.yaml` shows every required field.

Common tasks:

- **New job** → add an entry under `sections.experience.entries` (newest first).
- **Achievements for a job** → add a `highlights:` list to that entry — the best
  place for numbers (“cut report latency by 40 %”).
- **New skill row** → add to `sections.skills.groups` (`level: ""` hides the level
  chip for one row).
- **Re-colour everything** → change `theme.bar` / `theme.accent` / … and run
  `python scripts/generate.py`: the PDF *and* the web page pick it up.
- **Change the fonts** → `fonts.latex` must be a package shipped with TeX Live,
  `fonts.html` a Google-Fonts family (the stylesheet URL is generated from it).
- **Hide the site from search engines** → `meta.noindex: true`.
- **Rename the file the browser saves** → `meta.pdf_download_name`
  (e.g. `Firstname_Lastname_CV.pdf`).
- **A variant for another role** → copy `data/cv.yaml` (e.g. `data/cv-backend.yaml`)
  and change the one path in `scripts/generate.py`.

## 🎨 Changing the look

| Layer | File | Contains |
| --- | --- | --- |
| Content | `data/cv.yaml` | all text + palette + margins |
| PDF design | `src/cv.tex` + `src/cvstyle.tex` | section order, fonts, macros (`\cvsection`, `\cventry`, `\cvtech`, …), spacing |
| Web design | `templates/index.html` + `web/style.css` | page chrome, CSS grid/flex layout (colours and widths come from `data/cv.yaml`) |

Both renderings intentionally share one structure: centred header → contact line →
coloured section bars → entries with a right-aligned date → shaded “Technologies”
strips. If you change a spacing value in `src/cvstyle.tex`, change the matching
value in `web/style.css` so the two keep matching.

## 🛠️ Local build helpers

```bash
make gen          # data/cv.yaml -> src/generated/*.tex + web/index.html
make check        # validate.py + generate.py --check
make pdf          # gen + XeLaTeX  -> src/cv.pdf + dist/cv.pdf
make preview      # gen + pdf + web/preview.png        (needs: pip install pypdfium2)
make protected PASSCODE="the-code"                     # dist/cv-protected.pdf
make encrypt      # data/cv.yaml -> data/cv.yaml.age   (commit this one)
make decrypt      # data/cv.yaml.age -> data/cv.yaml
make clean
```

Windows equivalents:

```powershell
.\build.ps1
.\build.ps1 -Preview
.\build.ps1 -Protected "the-code"

powershell -ExecutionPolicy Bypass -File .\scripts\crypt.ps1 encrypt
powershell -ExecutionPolicy Bypass -File .\scripts\crypt.ps1 decrypt
```

`data/cv.example.yaml`, the Makefile and `scripts/crypt.ps1` expect the age key at
`~/.age/cv-key.txt` (`%USERPROFILE%\.age\cv-key.txt` on Windows); override with
`AGE_KEY_FILE` / `-KeyFile` or the `CV_AGE_KEY_FILE` environment variable.

## 🔒 Keeping it private

A GitHub Pages site cannot be made private on a free (or Pro) account — private
Pages is a GitHub Enterprise Cloud feature — so this project protects the *content*
rather than the *page*:

| Where | What sits there | Protected by |
| --- | --- | --- |
| the repository | `data/cv.yaml.age` — your content, encrypted with [age](https://age-encryption.org) | X25519 + ChaCha20-Poly1305; the key never enters git |
| the git history | the same ciphertext (the clear file and every rendering are gitignored) | nothing readable |
| GitHub Pages | StatiCrypt-encrypted page + AES-256 encrypted PDF | the code |
| GitHub Releases | the encrypted PDF (`cv.pdf`) | the code |
| workflow artifacts | only the encrypted PDF (`cv-pdf-protected`) | the code |
| CI logs | fingerprints (`len=… sha256=…`), never your text | by design — the logs of a public repository are world-readable |

**The identity key is the single point of failure.** Keep a copy in a password
manager: lose it and the committed ciphertext can never be decrypted; leak it and
your content can be read. To rotate it:

```bash
age-keygen -o ~/.age/new-key.txt
make encrypt AGE_KEY_FILE=~/.age/new-key.txt     # re-encrypt the source with the new key
# then update the AGE_KEY secret and re-run the workflow
```

**Still public:** `web/style.css` (CSS only, no content) and the fact that the
repository exists. The encrypted page reveals nothing about you — not even its
title — until the code is typed. That code is shared with everyone you hand it to,
so rotate it per employer and never reuse a password you use elsewhere. If you want
a real gatekeeper instead of client-side encryption, put the site behind
**Cloudflare Access** (free for up to 50 users): it checks who is asking before any
content is served.

## ✅ How the rules are enforced

| Guard | What it catches |
| --- | --- |
| `scripts/validate.py` — **age drift check** | you edited `data/cv.yaml` and forgot to re-encrypt it (the committed `.age` no longer matches) |
| `scripts/validate.py` — sync check | a value from the YAML missing from the LaTeX *or* the HTML; `\input` targets that do not exist; unbalanced braces / `\begin`…`\end`; a generated section `src/cv.tex` forgot to include; broken HTML tag nesting; leftover `{{TEMPLATE}}` tokens; invalid workflow YAML |
| `scripts/check_site.py` | anything about to be published that still contains the CV in clear text: the page must carry the StatiCrypt marker and **every PDF must require a password** |
| build guards (`main` and tags) | a missing `AGE_KEY` or `CV_PDF_PASSWORD`: the build fails instead of publishing a readable CV |

`validate.py` and `check_site.py` print **fingerprints** (`len=… sha256=…`) instead
of the offending text, because the logs of a public repository are world-readable.
Run `python scripts/check_site.py <dir> --show-text` locally when you need the real
strings.

## 🚀 CI/CD

- **`build-cv.yml`** — on pushes to the branches listed in the workflow, on tags
  and on manual runs (pull requests from forks are skipped: they cannot read
  repository secrets). A branch that carries no CV source skips the build with a
  warning, so a tooling-only branch (e.g. the public template) stays green:
  install `age` → **decrypt `data/cv.yaml.age`** (`AGE_KEY`) → `generate.py` →
  XeLaTeX compile → **encrypt the PDF** (`CV_PDF_PASSWORD`) → build `_site/`
  (encrypted `cv.pdf` + **StatiCrypt-encrypted page**) → `check_site.py` → upload
  the encrypted artifact → upload the Pages artifact → (on a tag) attach the
  encrypted `cv.pdf` to the Release → deploy to Pages.
- **`lint.yml`** — decrypt + generate + `validate.py`, plus a non-blocking
  codespell run.
- **Releasing:** `git tag v2026.11 && git push origin v2026.11` creates a Release
  with the **encrypted** `cv.pdf` attached (that is what
  `releases/latest/download/cv.pdf` serves) and auto-generated notes.

One-time repository setup:

1. **Settings → Pages → Build and deployment → Source:** `GitHub Actions`.
   ⚠️ **Not optional.** While the source is a *branch*, GitHub runs its own Jekyll
   build on **every** push and publishes the whole repository in clear text, racing
   with (and sometimes overwriting) the site this workflow deploys. For the same
   reason never add a second Pages workflow (e.g. the Jekyll starter workflow):
   both would deploy to the same `github-pages` environment.
2. **If the branch carrying your content is not your default branch**, allow it to
   deploy: **Settings → Environments → `github-pages` → Deployment branches and
   tags** → add that branch (or choose *All branches*). Without this the build
   succeeds but the deploy job fails with *“Branch … is not allowed to deploy to
   github-pages due to environment protection rules.”*
3. **Settings → Actions → General → Workflow permissions:** read/write — the
   Release step needs it.
4. **Settings → Secrets and variables → Actions:**
   * `AGE_KEY` = the whole content of your age identity file (`~/.age/cv-key.txt`).
     The workflow extracts the key itself, so a CRLF or single-line paste is fine —
     what it cannot do is guess a key that is not there.
   * `CV_PDF_PASSWORD` = the code you hand out, **14+ characters** recommended: the
     encrypted page is public, so a short code can be brute-forced offline.
     (StatiCrypt warns below 14 characters; the build passes `--short` and keeps
     going.)
5. Push a tag once to create the first Release.
6. Optional: keep **Settings → Actions → General → Artifact and log retention**
   short — every run recreates the (encrypted) artifacts anyway.

If a step fails, the guards print the reason as a **check annotation** (Actions →
the run → Annotations), so you rarely need the raw log: `AGE_KEY is not set`,
`age could not decrypt data/cv.yaml.age`, `AGE_KEY does not contain an age
identity`, `Refuse to publish an unprotected CV`, and so on.

## ⚠️ Note on layout vs ATS

The design is a classic CV layout: centred header, coloured section bars, a skills
table, right-aligned dates. Pleasant to read, slightly less machine-friendly than a
plain single-column document.

- ✅ Text is selectable, fonts are embedded, PDF metadata (`pdftitle`, `pdfauthor`,
  keywords) is set, and the web page carries schema.org `Person` JSON-LD — most
  ATS/parsers handle it.
- ⚠️ If an application form demands plain text, copy it from the web page or build a
  single-column variant (a few lines in `src/cvstyle.tex`).
- Tip: the name the browser saves the file as comes from `meta.pdf_download_name`
  (e.g. `Firstname_Lastname_CV.pdf`), so set it once instead of renaming by hand.

## 📄 Licence

Two parts, two sets of terms — full text in [LICENSE](./LICENSE):

| Part | Covers | Terms |
| --- | --- | --- |
| **A. Tooling** | `scripts/`, `.github/workflows/`, `Makefile`, `build.ps1`, `templates/`, `web/style.css` | **MIT** — copy, modify, reuse, including commercially |
| **B. Personal CV content** | `data/cv.yaml` / `data/cv.yaml.age`, the rendered `cv.pdf` and `web/index.html`, `web/preview.png` | **All rights reserved** — do not reuse someone else's CV |

**If you fork this repository:** part A is what you came for — take it freely and
replace part B with your own name and notice. The repository ships only the
encrypted blob, so a fork contains nothing readable to begin with; delete
`data/cv.yaml.age` anyway and start from `data/cv.example.yaml`.




