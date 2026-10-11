# my-cv - encrypt / decrypt the CV source (Phương án D)
#
# The content lives in data/cv.yaml (gitignored, clear text). The repository
# carries data/cv.yaml.age - the same file, encrypted with age - so the public
# repo never contains the CV. CI decrypts it with the AGE_KEY secret.
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File .\scripts\crypt.ps1 encrypt   # clear -> .age  (then commit)
#   powershell -ExecutionPolicy Bypass -File .\scripts\crypt.ps1 decrypt   # .age  -> clear
#
# The private key must NOT live in the repository. Default location:
#   %USERPROFILE%\.age\cv-key.txt        (create it once with: age-keygen -o <path>)
# Override with -KeyFile <path> or the CV_AGE_KEY_FILE environment variable.

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true, Position = 0)]
    [ValidateSet('encrypt', 'decrypt')]
    [string]$Action,

    [string]$KeyFile = $(if ($env:CV_AGE_KEY_FILE) { $env:CV_AGE_KEY_FILE } else { "$HOME\.age\cv-key.txt" })
)

$ErrorActionPreference = 'Stop'
Set-Location (Join-Path $PSScriptRoot '..')

if (-not (Get-Command age -ErrorAction SilentlyContinue)) {
    Write-Error "age not found on PATH. Install it with:  winget install FiloSottile.age   (then open a new terminal)"
}
if (-not (Test-Path $KeyFile)) {
    Write-Error "age identity key not found: $KeyFile`nCreate one with:  age-keygen -o `"$KeyFile`""
}

$recipient = (Get-Content $KeyFile | Select-String 'public key:').Line -replace '.*public key: ', ''
$recipient = $recipient.Trim()

switch ($Action) {
    'encrypt' {
        if (-not (Test-Path 'data/cv.yaml')) { Write-Error "data/cv.yaml is missing - run: age -d -i `"$KeyFile`" -o data/cv.yaml data/cv.yaml.age" }
        age -e -r $recipient -o data/cv.yaml.age data/cv.yaml
        $clear = (Get-Item data/cv.yaml).Length
        $cipher = (Get-Item data/cv.yaml.age).Length
        Write-Host "encrypted data/cv.yaml ($clear B) -> data/cv.yaml.age ($cipher B)"
        Write-Host "now run:  python scripts/generate.py ; python scripts/validate.py ; git add data/cv.yaml.age"
    }
    'decrypt' {
        if (-not (Test-Path 'data/cv.yaml.age')) { Write-Error "data/cv.yaml.age is missing" }
        age -d -i $KeyFile -o data/cv.yaml data/cv.yaml.age
        Write-Host "decrypted data/cv.yaml.age -> data/cv.yaml ($((Get-Item data/cv.yaml).Length) B)"
    }
}
