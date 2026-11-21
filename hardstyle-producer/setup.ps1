# hardstyle-producer setup (Windows PowerShell). Installs ONLY into an isolated venv inside this skill folder.
$ErrorActionPreference = "Stop"
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
$py = $null
foreach ($v in @("3.12", "3.11")) { try { & py -$v --version *> $null; if ($LASTEXITCODE -eq 0) { $py = @("py", "-$v"); break } } catch {} }
if (-not $py) { Write-Host "Fant ikke Python 3.11/3.12. Installer: winget install Python.Python.3.12"; exit 1 }
if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) { Write-Host "ADVARSEL: ffmpeg mangler. Installer: winget install Gyan.FFmpeg" }
& $py[0] $py[1] -m venv "$Here\.venv"
& "$Here\.venv\Scripts\python.exe" -m pip install -q --upgrade pip
& "$Here\.venv\Scripts\pip.exe" install -q -r "$Here\requirements.txt"
& "$Here\.venv\Scripts\pip.exe" install -q --no-deps "basic-pitch==0.4.0"
New-Item -ItemType Directory -Force "$HOME\.claude\commands" | Out-Null
Copy-Item "$Here\commands\*.md" "$HOME\.claude\commands\" -Force
Write-Host "Kjører selvtest ..."
& "$Here\bin\hsp.ps1" diagnose
& "$Here\.venv\Scripts\python.exe" "$Here\tests\selftest.py"
