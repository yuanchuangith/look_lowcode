[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$python = (Get-Command python.exe -ErrorAction Stop).Source
& $python (Join-Path $PSScriptRoot 'setup.py')
exit $LASTEXITCODE
