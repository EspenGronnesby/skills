$Here = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$env:PYTHONPATH = "$Here\scripts"
& "$Here\.venv\Scripts\python.exe" -m hsp @args
exit $LASTEXITCODE
