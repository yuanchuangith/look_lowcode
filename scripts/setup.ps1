[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$pluginRoot = Split-Path -Parent $PSScriptRoot
$python = (Get-Command python.exe -ErrorAction Stop).Source
& $python (Join-Path $PSScriptRoot 'setup.py')
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Write-Host "Next: run scripts\configure_connection.ps1"
Write-Host "CPM snapshot: run scripts\configure_cpm.ps1"
