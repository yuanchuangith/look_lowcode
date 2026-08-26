[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$pluginRoot = Split-Path -Parent $PSScriptRoot
$runtimeRoot = Join-Path $env:LOCALAPPDATA 'GxpLowcodeReadonly'
$venvPath = Join-Path $runtimeRoot '.venv'
$pythonPath = Join-Path $venvPath 'Scripts\python.exe'

New-Item -ItemType Directory -Path $runtimeRoot -Force | Out-Null
if (-not (Test-Path -LiteralPath $pythonPath)) {
    python -m venv $venvPath
}

& $pythonPath -m pip install --disable-pip-version-check --upgrade pip
& $pythonPath -m pip install --disable-pip-version-check -r (Join-Path $pluginRoot 'requirements.txt')
Write-Host "Runtime ready: $venvPath"
Write-Host "Next: run scripts\configure_connection.ps1"
