# CV as Code

> One YAML file in — a consistent LaTeX PDF and a matching web page out, built and
> published by GitHub Actions. The CV text lives in a **private** data repository;
> every published page sits **behind a code**.

This repository is **tooling + the published site**: it contains no personal data.
The content lives in the private repository `cv-private`, one file per CV, and CI
reads it through a **read-only deploy key**:

```
cv-private/ai/cv.yaml         -> https://YOUR-USER.github.io/YOUR-REPO/ai/
cv-private/backend/cv.yaml    -> https://YOUR-USER.github.io/YOUR-REPO/backend/
cv-private/applications.json  -> https://YOUR-USER.github.io/YOUR-REPO/admin/
```

| You get | Built by | Published to |
| --- | --- | --- |
| `cv.pdf` (LaTeX / XeLaTeX) | GitHub Actions | **inside** its page — it has no URL of its own |
| `web/index.html` + `web/style.css` | GitHub Actions | GitHub Pages, page encrypted with StatiCrypt |
| `web/admin.html` | GitHub Actions | `/admin/`, protected by its own code |

## 🗂 Why a private data repository

- the CV text is versioned **in git** (`git log -p ai/cv.yaml` is the CV's own
  changelog) without ever entering a public repository — no `.age` blobs, no
  encrypt-before-push step, no drift checks;
- a public fork of this repository starts empty and stays empty;
- the only CV-related things published here are StatiCrypt-encrypted pages.

`main` is the only branch. Adding a third CV = a new folder with a `cv.yaml` in
`cv-private`: the build discovers every `<site>/cv.yaml`, compiles it, publishes
its page and adds it to the chooser — no workflow edit.

`scripts/check_site.py` guards the result: it verifies every page is encrypted, that
no `*.pdf` file was published, and that no string from **either** `cv.yaml` appears
in the clear (`--data` accepts one file per CV; `--allow-plain-index` is only for the
chooser page, which holds no CV content).

## ⚡ Quick start

```bash
git clone https://github.com/YOUR-USER/YOUR-REPO.git && cd YOUR-REPO
git clone git@github.com:YOUR-USER/cv-private.git ../cv-private   # the private data
python3 -m pip install pyyaml cryptography

# edit ../cv-private/ai/cv.yaml, then:
make gen   DATA=../cv-private/ai/cv.yaml    # YAML -> src/generated/*.tex + web/index.html
make check DATA=../cv-private/ai/cv.yaml    # must print: ALL STATIC CHECKS PASSED
make pdf   DATA=../cv-private/ai/cv.yaml    # needs xelatex + latexmk -> dist/cv.pdf
make pages DATA=../cv-private/ai/cv.yaml    # same, then print the page count

git -C ../cv-private commit -am "content: ..." && git -C ../cv-private push
gh workflow run build-cv.yml                # or wait for the dispatch / 6h schedule
```

That is the whole workflow: **edit the YAML in the private repo → render + validate →
push → CI publishes**. There is no encryption step, because the source never enters
this repository. Everything runs on **Linux or macOS** — GNU `make`, Python 3 and a
TeX distribution; there is no PowerShell and no `.ps1` here (Git Bash / WSL works on
Windows).

In a hurry? `scripts/update.sh --push -m "content: …"` does every step above in one
go — see [The daily loop](#-the-daily-loop).

## 🔁 The daily loop

One command runs the whole cycle — open `$EDITOR` on the private file → regenerate →
validate → (optionally) commit and push **in the data repository**:

```bash
scripts/update.sh                          # edit ../cv-private/ai/cv.yaml
scripts/update.sh --site backend           # edit the backend CV instead
scripts/update.sh --commit -m "content: new role"
scripts/update.sh --push -m "content: new role"
scripts/update.sh --no-edit                # no editor: just render + validate
```

It prints `>> generating … from ../cv-private/ai/cv.yaml` → `ALL STATIC CHECKS
PASSED`, then either prints the two git commands to run, or commits/pushes in
`cv-private` and asks GitHub Actions to rebuild the site.

Prefer to drive each step yourself?

```bash
$EDITOR ../cv-private/ai/cv.yaml
make gen   DATA=../cv-private/ai/cv.yaml    # -> src/generated/*.tex + web/index.html
make check DATA=../cv-private/ai/cv.yaml    # validate.py + generate.py --check
git -C ../cv-private commit -am "content: ..." && git -C ../cv-private push
```

On a push to `cv-private`, its `dispatch-cv.yml` sends a `repository_dispatch` here.
This workflow then checks out both repositories, renders each `*/cv.yaml`, compiles
the PDF, embeds it in the page, encrypts the page with StatiCrypt (`CV_PDF_PASSWORD`),
verifies that nothing readable survives, and deploys to Pages. Nothing else is
published: no Release, no artifact, no `cv.pdf` URL.

`scripts/validate.py --data <file>` is the local guard (schema, unknown keys, YAML
hygiene, LaTeX/HTML sync); in CI it runs for **both** CV files, and
`scripts/test_validate.py` proves the guard still fires by feeding it broken copies.

## 🧰 Commands

| Command | What it does |
| --- | --- |
| `make help` | list every target |
| `make update` / `scripts/update.sh` | the whole edit cycle: `$EDITOR` on the private YAML → generate → validate (`--commit` / `--push` to publish in `cv-private`) |
| `make` / `make pdf` | generate + compile the PDF → `dist/cv.pdf` |
| `make pages` | `pdf` + report the page count (`PAGE_LIMIT=2` fails when the CV gets longer) |
| `make gen DATA=<file>` | CV YAML → `src/generated/*.tex` + `web/index.html` |
| `make check DATA=<file>` | `validate.py` + `generate.py --check` — run before every commit |
| `make site` | + `_site/` with the PDF embedded, exactly like CI (open it in a browser) |
| `make protected PASSCODE="…"` | + `dist/cv-protected.pdf` (hand-out copy that asks for a code) |
| `make admin` | render `web/admin.html` (local preview; CI encrypts it into `/admin/`) |
| `make history SITE=ai` | copy `dist/cv.pdf` into the data repo's `cv-history/` (a plain PDF, so it never touches the site) |
| `make clean` | remove the LaTeX aux files and `dist/` |

Without GNU `make`, the shell script does the same work:

```bash
scripts/build.sh --help          # --site  --protected CODE  --data FILE
scripts/build.sh --site          # = make site
scripts/build.sh --data ../cv-private/backend/cv.yaml
```

CI reaches the private data repository through a **read-only deploy key**
(`Settings → Deploy keys` on `cv-private`, public key only). Its private half is the
repository secret `CV_DATA_DEPLOY_KEY`; nothing else is needed, and the key expires
only when you delete it.

## 📦 Install the tools

| To do this | You need |
| --- | --- |
| Edit content | Python 3 + `python3 -m pip install pyyaml` |
| Build the PDF locally | a TeX distribution with `xelatex` + `latexmk` — *or* skip it: CI compiles |
| Encrypt the source | [age](https://age-encryption.org) |
| Run the pipeline | a GitHub repository with Actions + Pages (the free plan is enough) |

```bash
# Debian / Ubuntu
sudo apt install make python3 python3-pip latexmk texlive-xetex \
                 texlive-latex-extra texlive-fonts-recommended texlive-fonts-extra
python3 -m pip install pyyaml cryptography

# Fedora
sudo dnf install make python3 python3-pip latexmk texlive-xetex texlive-scheme-medium

# macOS
brew install make python3
brew install --cask mactex-no-gui      # or: brew install tectonic
```

`texlive-fonts-extra` is only needed for the `sourceserifpro` font the PDF uses; if
it is missing, `src/cvstyle.tex` falls back to DejaVu Serif and the build still works.

## 🚀 Use it for your own CV

1. **Fork / clone / “Use this template”** — this repository is tooling only, it
   carries no personal data, so a fork starts clean.

2. **Create the private data repository** (`YOUR-USER/cv-private`) with one file per
   CV. `data/cv.example.yaml` is a complete, valid starter:

   ```bash
   mkdir -p ../cv-private/ai && cp data/cv.example.yaml ../cv-private/ai/cv.yaml
   # a second CV:  mkdir -p ../cv-private/backend && cp data/cv.example.yaml ../cv-private/backend/cv.yaml
   ```

   `YOUR-USER`, `YOUR-REPO`, `Your Name`, `Your Job Title` and `you@example.com` are
   the only personal placeholders; nothing in `scripts/`, `templates/` or the
   workflows is personal.

3. **Render and check** against that file:

   ```bash
   make gen   DATA=../cv-private/ai/cv.yaml
   make check DATA=../cv-private/ai/cv.yaml    # must print: ALL STATIC CHECKS PASSED
   ```

4. **Give CI read access to the data repository** — `cv-private → Settings → Deploy
   keys → Add deploy key`, paste a **public** key and leave *Allow write access*
   unchecked. Then store the private half here:

   ```bash
   ssh-keygen -t ed25519 -N '' -C 'cv-ci-read-only' -f ~/.ssh/cv-data
   gh repo deploy-key add ~/.ssh/cv-data.pub -R YOUR-USER/cv-private --title 'cv CI (read-only)'
   gh secret set CV_DATA_DEPLOY_KEY -R YOUR-USER/YOUR-REPO < ~/.ssh/cv-data
   ```

5. **Add the other secrets** (`Settings → Secrets and variables → Actions`):

   | Secret | Used for |
   | --- | --- |
   | `CV_DATA_DEPLOY_KEY` | reading `cv-private` (step 4) |
   | `CV_PDF_PASSWORD` | the code that opens `/ai/` and `/backend/` (14+ characters) |
   | `CV_ADMIN_PASSWORD` | the code that opens `/admin/` (optional; without it no admin page is published) |

   In `cv-private`, add `CV_DISPATCH_TOKEN` (fine-grained PAT, *Contents: read and
   write* on **this** repository only) so a data push rebuilds the site by itself.

6. **Turn on Pages**: *Settings → Pages → Build and deployment → Source = GitHub
   Actions*, and *Settings → Actions → General → Workflow permissions = Read and
   write* (every run uploads the Pages artifact).

7. **Build** — the workflow reads the data repository, renders every `*/cv.yaml`,
   compiles, encrypts and deploys:

   ```bash
   git add -A && git commit -m "my CV" && git push
   gh workflow run build-cv.yml          # or push to cv-private, or wait for the schedule
   ```

Your site is then at `https://YOUR-USER.github.io/YOUR-REPO/`: type the code and the
page shows, with the PDF downloadable from the two buttons in the toolbar (the PDF
lives inside that page — there is no separate PDF URL, no Release asset and no
workflow artifact to fetch). Optional badge for the top of your README:

```markdown
[![build](https://github.com/YOUR-USER/YOUR-REPO/actions/workflows/build-cv.yml/badge.svg)](https://github.com/YOUR-USER/YOUR-REPO/actions/workflows/build-cv.yml)
```

## 📁 Project structure

```
.
├─ data/
│  └─ cv.example.yaml          a complete starter: copy it into the data repository
├─ src/
│  ├─ cv.tex                   entry point: section order (XeLaTeX)
│  ├─ cvstyle.tex              look & feel of the PDF (fonts, macros, spacing)
│  └─ generated/               ⟵ built from the CV YAML, never committed
├─ templates/
│  ├─ index.html               shell of the CV page (placeholders only)
│  └─ admin.html               shell of the admin page (placeholders only)
├─ web/
│  ├─ index.html               ⟵ built from the CV YAML, never committed
│  ├─ admin.html               ⟵ built from templates/admin.html, never committed
│  ├─ style.css                look & feel of the CV page (CSS variables)
├─ scripts/
│  ├─ generate.py              CV YAML -> LaTeX + HTML          (--data <file>)
│  ├─ generate_admin.py        templates/admin.html -> web/admin.html
│  ├─ history_cv.py            record built PDFs in the data repo's cv-history/
│  ├─ embed_pdf.py             PDF -> base64 inside the page (no PDF URL)
│  ├─ validate.py              static checks                    (--data <file>)
│  ├─ test_validate.py         fault injection for validate.py
│  ├─ update.sh                one command: edit -> gen -> check -> commit/push
│  ├─ build.sh                 local build (= make pdf / site / protected)
│  ├─ protect_pdf.py           optional: AES-256-encrypt a PDF for a hand-out
│  ├─ check_site.py            fails the build if _site still has plain text
├─ .github/workflows/
│  ├─ build-cv.yml             data repo -> generate -> compile -> embed + encrypt -> Pages
│  └─ lint.yml                 generate + validate every CV + spell check
├─ Makefile                    local helpers (run: make help)
└─ LICENSE
```

**Not committed** (all in `.gitignore`): `src/generated/`, `web/index.html`,
`web/admin.html`, `dist/`, `_site/`, a stray local `data/cv.yaml`,
and local notes such as `Agent.md` or `.secrets`.

## 🔧 How the pipeline works

```
   cv-private/ai/cv.yaml      ← the private data repository (read-only deploy key)
             │  checkout with ssh-key: CV_DATA_DEPLOY_KEY
             ▼
   build/<site>/data/cv.yaml  ← a copy of the tooling for that site + its CV
             │
   scripts/generate.py --data …
      ├──► src/generated/*.tex ── XeLaTeX ──► src/cv.pdf
      └──► web/index.html
                    │
        scripts/validate.py  → fails if a section is missing, or if a value from
                               the YAML is not in BOTH renderings
                    │
        scripts/embed_pdf.py → cv.pdf becomes base64 *inside* the page,
                               so no /cv.pdf exists to fetch
                    │
        StatiCrypt (CI)      → encrypts that page with CV_PDF_PASSWORD
                    │
             _site/ai/ + _site/backend/  (one encrypted index.html each)
                    └──► GitHub Pages
                    │
        scripts/check_site.py → fails if a page is not StatiCrypt-encrypted, if a
                                separate PDF turned up, or if any published file
                                carries a CV in the clear
```

The repository only ever carries ciphertext, and GitHub Pages serves exactly one
encrypted page. The PDF is inside that page, so it is reachable only after the code
is typed — while the PDF *file* itself carries no password and opens in any reader
once it has been downloaded.

## 🛠 The admin page (`/admin/`)

A second StatiCrypt-protected page with its **own** code (`CV_ADMIN_PASSWORD`). It
answers “which CV did I send where, and when?” and hands back older PDFs.

| Tab | What it shows |
| --- | --- |
| **Đơn đã gửi** | every application: date, company, role, channel, which CV, **which snapshot** was sent, status, follow-up, notes — with search, filters and counters (total, per CV, interviews, rejections, last 30 days) |
| **Bản CV** | the snapshots from `cv-history/` in the data repository, with page count and size; **Tải PDF** downloads one straight from there |
| **Cài đặt** | the GitHub token (kept in `localStorage` of that browser only) |

The data lives in the private repository as `applications.json`:

```json
{
  "schema": 1,
  "applications": [
    { "id": "app-abc", "sent": "2026-11-15", "company": "FPT Software",
      "role": "Senior Backend Engineer", "channel": "LinkedIn",
      "cv": "backend", "cv_version": "backend@d5f6ced",
      "status": "sent", "follow_up": "2026-11-22", "contact": "HR Hoa",
      "notes": "JD nhấn Kafka" }
  ]
}
```

The page calls `api.github.com` **directly from the browser** with a fine-grained PAT
you paste once per device (*Contents: read and write* on the data repository only).
No server is involved and the token never reaches this repository.

### CV history (“tải lại CV cũ”)

Every build copies the two PDFs into the **private** repository:

```
cv-private/cv-history/ai/2026-11-15-ai-1a2b3c4.pdf
cv-private/cv-history/backend/2026-11-15-backend-1a2b3c4.pdf
cv-private/cv-history/index.json
```

`<sha>` is the commit of the data repository the PDF was rendered from, so
`git -C ../cv-private show <sha>` explains each snapshot, and `index.json` carries
the page count and size the admin page shows.

A plain PDF can never be served by a static host, which is exactly why it lives
there instead of next to the site: the admin page reads `cv-history/index.json` and
the PDF bytes through `api.github.com` with your token (`Accept:
application/vnd.github.raw`), then saves the file from a blob URL.

```bash
make history SITE=ai                            # from dist/cv.pdf
python3 scripts/history_cv.py list --root ../cv-private/cv-history
python3 scripts/history_cv.py add --root ../cv-private/cv-history --force \
  --site ai --pdf dist/cv.pdf --version ai@manual --pages 2
```

CI records one snapshot per data revision (a rebuild of the same revision is a
no-op, `--force` replaces one) and keeps the newest 20 per CV.

## ✍️ Editing the content (`data/cv.yaml`)

Everything is plain text — you never write LaTeX or HTML by hand; `%`, `&`, `_`,
quotes and dashes are escaped for you.

```yaml
meta:                     # name, role, contact details, page/PDF titles, links …
theme:                    # the palette used by BOTH renderings
fonts:                    # latex: a font shipped with TeX Live | html: a Google-Fonts family
layout:                   # PDF margins + the maximum width of the web page
sections:
  summary:              { title: Profile Summary, text: "…" }
  experience_projects:  { title: Experience & Projects, entries: [ {name, role,
                          company, dates, description, technologies_tools?,
                          responsibilities[], achievements[]} ] }
  projects:             { title: Projects, entries: [ {name, role?, dates?,
                          link_label?, link_url?, description?,
                          technologies_tools?, responsibilities[], achievements[]} ] }
  skills:               { title: Skills, groups: [ {name, items, level?} ] }
  education:            { title: Education, entries: [ {school, major, dates?} ] }
  languages:            { title: Languages, entries: [ {name, score} ] }
  certificates:         { title: Certifications, entries: [ {name, issuer, issued,
                                                             expires, credential_id?} ] }
```

`sections` must contain exactly those seven keys, and the order in which they are
rendered is fixed in `SECTION_ORDER` inside `scripts/generate.py` — not by the
order in the file. A section *key* is only an internal name (it becomes the file
name `src/generated/<key>.tex` and the HTML id); what a reader — and an ATS —
sees is the section `title:`, so name the title the way the job ads do
(`Work Experience`, `Skills`, `Certifications`, …).

`sections.projects` is where work **without an employer** goes: personal and side
projects. It has no `company`; `link_label` + `link_url` render as a clickable
link under the headline (the label is what a reader sees, so keep it short —
`github.com/you/project`). Like the other sections it must exist — the validator
rejects a missing section — but its `entries` list is entirely yours.

An entry of `experience_projects` can describe a role, a project or both:
`name` / `role` / `company` / `dates` are required and `description` /
`technologies_tools` / `responsibilities` / `achievements` are optional, so an
entry is only as long as you need. `data/cv.example.yaml` shows every field, and
`python3 scripts/validate.py --data ../cv-private/ai/cv.yaml` lints the structure
(unknown keys, missing keys, duplicate keys, a `#` that YAML keeps as text, date
ranges that overlap, …). `python3 scripts/test_validate.py --data …` proves that lint
actually fires, by feeding it 14 deliberately broken copies of the file (schema keys
only, so the test file itself carries no CV content).

Common tasks:

- **New role or project** → add an entry under
  `sections.experience_projects.entries` (newest first).
- **Side project** → add an entry under `sections.projects.entries` (no employer;
  `link_label` + `link_url` replace the company).
- **GitHub in the header** → `meta.github_label` + `meta.github_url` (both
  optional: drop them and the header has no GitHub link).
- **Achievements** → the `achievements:` list of that entry — the best place for
  numbers (“cut report latency by 40 %”).
- **New skill row** → add to `sections.skills.groups` (`level: ""` hides the level
  chip for one row).
- **Re-colour everything** → change `theme.bar` / `theme.accent` / … and run
  `make gen DATA=<file>`: the PDF *and* the web page pick it up.
- **Change the fonts** → `fonts.latex` must be a package shipped with TeX Live,
  `fonts.html` a Google-Fonts family (the stylesheet URL is generated from it).
- **Hide the site from search engines** → `meta.noindex: true`.
- **Rename the file the browser saves** → `meta.pdf_download_name`, with `{date}`
  expanded to DDMMYYYY when the page is published
  (e.g. `FirstName{date}SeniorAIEngineer.pdf` → `FirstName15112026SeniorAIEngineer.pdf`).
- **A variant for another role** → add another folder in the data repository
  (`devops/cv.yaml`), push, and CI discovers it: `/cv/devops/` is built, added to
  the chooser (set `meta.site_label` / `meta.site_summary`) and recorded in
  `cv-history/`; locally `make pdf DATA=../cv-private/devops/cv.yaml`.

## 🎨 Changing the look

| Layer | File | Contains |
| --- | --- | --- |
| Content | `data/cv.yaml` | all text + palette + margins |
| PDF design | `src/cv.tex` + `src/cvstyle.tex` | section order, fonts, macros (`\cvsection`, `\cvxpentry`, `\cvdesc`, `\cvtech`, …), spacing |
| Web design | `templates/index.html` + `web/style.css` | page chrome, CSS grid/flex layout (colours and widths come from `data/cv.yaml`) |

Both renderings intentionally share one structure: centred header → contact line →
coloured section bars → entries with a right-aligned date → shaded “Technologies”
strips. If you change a spacing value in `src/cvstyle.tex`, change the matching
value in `web/style.css` so the two keep matching.

## 🔒 Keeping it private

Both renderings are produced from the same source, so the palette, fonts and
margins can never drift apart. One code (`CV_PDF_PASSWORD`) **encrypts the web
page**: StatiCrypt asks for it before showing anything, and the PDF travels
*inside* that page — it is the only copy that exists, so there is no `/cv.pdf`
URL to fetch and the PDF itself needs no password.

A GitHub Pages site cannot be made private on a free (or Pro) account — private
Pages is a GitHub Enterprise Cloud feature — so this project protects the *content*
rather than the *page*:

| Where | What sits there | Protected by |
| --- | --- | --- |
| this repository | nothing about the CV: tooling and docs | it simply carries no content |
| the data repository (private) | `ai/cv.yaml`, `backend/cv.yaml`, `applications.json`, `cv-history/*.pdf` | repository visibility; CI reads it with a read-only deploy key, the browser with your PAT |
| GitHub Pages | **StatiCrypt-encrypted pages** that *contain* their PDF (base64) | `CV_PDF_PASSWORD` (`/ai/`, `/backend/`) and `CV_ADMIN_PASSWORD` (`/admin/`) |
| `cv-history/*.pdf` | old CV snapshots (private, in the data repository) | repository visibility; the admin page needs your PAT to read them |
| Releases / artifacts | nothing — the workflow creates neither | — |
| CI logs | fingerprints (`len=… sha256=…`), never your text | by design — the logs of a public repository are world-readable |

**The PDF has no URL.** It is embedded in the page (`scripts/embed_pdf.py`) and
encrypted together with it, so a visitor must type `CV_PDF_PASSWORD` before the
download buttons work; `releases/latest/download/cv.pdf` and `…/cv.pdf` do not
exist. The PDF *file* itself carries no password: after the download it opens in any
reader, so recruiters never have to type anything twice.

That also means the file only reaches someone you gave the code (or the page) to.
If you would rather hand out a *revocable* file — one code for one recruiter —
encrypt a copy locally and send that instead:

```bash
make protected PASSCODE="the-code"      # dist/cv-protected.pdf — asks for the code
```

**`CV_ADMIN_PASSWORD` only gates `/admin/`.** It encrypts that page and nothing
else: the snapshots are plain PDFs in the private repository, so rotating the code
never locks you out of them (the CVs are rebuilt from the data repository anyway).
To rotate it:

```bash
gh secret set CV_ADMIN_PASSWORD -R YOUR-USER/YOUR-REPO
gh workflow run build-cv.yml -R YOUR-USER/YOUR-REPO        # secrets are read at run time
```


**The PAT you paste into `/admin/`** lives in that browser's `localStorage`. Give it
the smallest possible scope (a fine-grained token, *Contents: read and write* on the
data repository only, with an expiry) and revoke it there if a device is lost; the
page works read-only as soon as it is gone.

**Still public:** `web/style.css` (CSS only, no content) and the fact that the
repository exists. The encrypted page reveals nothing about you — not even its
title — until the code is typed, and the PDF stays sealed inside it. That code is
shared with everyone you hand it to, so rotate it per employer and never reuse a
password you use elsewhere. If you want a real gatekeeper instead of client-side
encryption, put the site behind **Cloudflare Access** (free for up to 50 users): it
checks who is asking before any content is served.

## ✅ How the rules are enforced

| Guard | What it catches |
| --- | --- |
| `scripts/validate.py` — sync check | a value from the YAML missing from the LaTeX *or* the HTML; `\input` targets that do not exist; unbalanced braces / `\begin`…`\end`; a generated section `src/cv.tex` forgot to include; broken HTML tag nesting; leftover `{{TEMPLATE}}` tokens; invalid workflow YAML |
| `scripts/check_site.py` | anything about to be published that still contains a CV in clear text: each page must carry the StatiCrypt marker, no `*.pdf` file may sit next to it (the PDF is embedded in the page), and no published file may contain a `cv.yaml` string in its raw bytes |
| build guards | a missing `CV_DATA_DEPLOY_KEY`, `CV_PDF_PASSWORD` or `cv-data/<site>/cv.yaml`: the build fails instead of publishing an empty or readable page |

`validate.py` and `check_site.py` print **fingerprints** (`len=… sha256=…`) instead
of the offending text, because the logs of a public repository are world-readable.
Run `python3 scripts/check_site.py <dir> --show-text` locally when you need the real
strings.

## 🚀 CI/CD

- **`build-cv.yml`** — on a push to `main`, on `repository_dispatch` from
  `cv-private`, on a 6-hourly schedule and on manual runs: checkout this repository
  → checkout `cv-private` with the deploy key → render every `*/cv.yaml` →
  XeLaTeX compile → **embed each PDF in its page** → build `_site/` → **encrypt each
  page** with StatiCrypt (`CV_PDF_PASSWORD`) → build and encrypt `/admin/`
  (`CV_ADMIN_PASSWORD`) → record both PDFs in `cv-history/` → `check_site.py` → upload the Pages
  artifact → deploy. Nothing else is published: no Release, no artifact, no `cv.pdf`
  URL. Before that it copies both PDFs into `cv-history/` in the data repository and
  commits them there with `[skip dispatch]`, so the data push cannot rebuild the
  site in a loop.
- **`lint.yml`** — validates **every** CV found in the data repository (plus the
  tooling), and runs a non-blocking codespell pass.
- **Releasing:** there is nothing to release. The site is always the latest build,
  and since no GitHub Release is created any more,
  `releases/latest/download/cv.pdf` is gone — **delete the Releases an older setup
  created** (Releases → the release → Delete) so the old link stops resolving too.

One-time repository setup:

1. **Settings → Pages → Build and deployment → Source:** `GitHub Actions`.
   ⚠️ **Not optional.** While the source is a *branch*, GitHub runs its own Jekyll
   build on **every** push and publishes the whole repository in clear text, racing
   with (and sometimes overwriting) the site this workflow deploys. For the same
   reason never add a second Pages workflow (e.g. the Jekyll starter workflow):
   both would deploy to the same `github-pages` environment.
2. **Settings → Actions → General → Workflow permissions:** *Read and write* — every
   run uploads the Pages artifact.
3. **Settings → Secrets and variables → Actions:**
   * `CV_DATA_DEPLOY_KEY` = the **private** half of the deploy key that has read
     access to your data repository (see
     [Use it for your own CV](#-use-it-for-your-own-cv) step 4).
   * `CV_PDF_PASSWORD` = the code you hand out for the **CV pages**, **14+
     characters** recommended: it is the only thing standing between a stranger and
     the page *and* the PDF inside it, so a short code can be brute-forced offline.
     (StatiCrypt warns below 14 characters; the build passes `--short` and keeps
     going.)
   * `CV_ADMIN_PASSWORD` = the code for `/admin/`. It gates that page only — the
     snapshots in `cv-history/` are unaffected by a change.
4. Delete any **Releases** older runs created (Settings → … → Releases): they still
   serve `releases/latest/download/cv.pdf`, and this setup no longer wants a public
   PDF link.
5. Optional: keep **Settings → Actions → General → Artifact and log retention**
   short — every run recreates the Pages artifact anyway.

If a step fails, the guards print the reason as a **check annotation** (Actions →
the run → Annotations), so you rarely need the raw log:
`CV_DATA_DEPLOY_KEY is missing`, `cv-data/<site>/cv.yaml is missing`,
`CV_PDF_PASSWORD is missing`, `Refuse to publish unprotected pages`, and so on.

## ⚠️ Note on layout vs ATS

The design is a classic CV layout: centred header, coloured section bars, a skills
table, right-aligned dates. Pleasant to read, slightly less machine-friendly than a
plain single-column document.

- ✅ Text is selectable, fonts are embedded, PDF metadata (`pdftitle`, `pdfauthor`,
  keywords) is set, and the web page carries schema.org `Person` JSON-LD — most
  ATS/parsers handle it.
- ⚠️ If an application form demands plain text, copy it from the web page or build a
  single-column variant (a few lines in `src/cvstyle.tex`).
- ⚠️ There is no public PDF URL any more (the file is inside the code-protected
  page), so a form cannot fetch it: unlock your page, download the PDF, upload that
  file. That is the point — the PDF is only reachable by someone who was given the
  code.
- Tip: the name the browser saves the file as comes from `meta.pdf_download_name`
  (e.g. `Firstname_Lastname_CV.pdf`), so set it once instead of renaming by hand.

## 📄 Licence

Two parts, two sets of terms — full text in [LICENSE](./LICENSE):

| Part | Covers | Terms |
| --- | --- | --- |
| **A. Tooling** | `scripts/` (`*.py`, `*.sh`), `.github/workflows/`, `Makefile`, `templates/`, `web/style.css` | **MIT** — copy, modify, reuse, including commercially |
| **B. Personal CV content** | the data repository (`ai/cv.yaml`, `backend/cv.yaml`, `applications.json`), the rendered `cv.pdf` and `web/index.html` | **All rights reserved** — do not reuse someone else's CV |

**If you fork this repository:** part A is what you came for — take it freely and
replace part B with your own content. A fork of this repository contains no CV at
all (the text lives in a separate private repository), so you start from
`data/cv.example.yaml` in a private repository of your own.




