# my-cv - local build script (Windows / PowerShell)
# Requires TeX Live or MiKTeX with 'xelatex' and 'latexmk' on PATH, plus Python
# with PyYAML:  python -m pip install pyyaml
#   (winget install TeXLive.TeXLive   |   choco install miktex)
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File .\build.ps1                 # content + PDF
#   powershell -ExecutionPolicy Bypass -File .\build.ps1 -Site           # + _site/ (PDF embedded)
#   powershell -ExecutionPolicy Bypass -File .\build.ps1 -Protected "code-for-hr"   # optional separate copy
#   powershell -ExecutionPolicy Bypass -File .\build.ps1 -Preview

[CmdletBinding()]
param(
    [string]$Protected,
    [switch]$Preview,
    [switch]$Site,
    [switch]$SkipGenerate
)

$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Error "python not found on PATH. Install Python 3 and 'python -m pip install pyyaml'."
}
if (-not (Get-Command latexmk -ErrorAction SilentlyContinue)) {
    Write-Error "latexmk not found. Install TeX Live or MiKTeX first."
}

# 1) Content: data/cv.yaml -> src/generated/*.tex + web/index.html
if (-not $SkipGenerate) {
    Write-Host ">> generating LaTeX + HTML from data/cv.yaml"
    python scripts/generate.py
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

# 2) PDF: compile inside src/ so that \input{...} resolves.
Push-Location src
latexmk -xelatex -interaction=nonstopmode -halt-on-error "cv.tex"
$code = $LASTEXITCODE
Pop-Location
if ($code -ne 0) { exit $code }

New-Item -ItemType Directory -Force -Path "dist" | Out-Null
Copy-Item "src/cv.pdf" "dist/cv.pdf" -Force
Write-Host "Built dist/cv.pdf"

# 3) Optional extras
if ($Preview) {
    python scripts/preview.py
}
# Assemble the page the way CI does: the PDF is embedded in it (no PDF URL of its
# own), so the last step of the build is that file plus style.css.
if ($Site) {
    New-Item -ItemType Directory -Force -Path "_site" | Out-Null
    Copy-Item "web/*" "_site/" -Recurse -Force
    Remove-Item "_site/index.html", "_site/preview.png", "_site/cv.pdf" -ErrorAction SilentlyContinue
    python scripts/embed_pdf.py --in "web/index.html" --pdf "dist/cv.pdf" --out "_site/index.html"
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    Write-Host "Open _site/index.html - CI then encrypts it with StatiCrypt (CV_PDF_PASSWORD)"
}
if ($Protected) {
    python scripts/protect_pdf.py --in "dist/cv.pdf" --password $Protected
}
