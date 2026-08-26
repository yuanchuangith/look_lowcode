[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$pluginRoot = Split-Path -Parent $PSScriptRoot
$pythonPath = Join-Path $env:LOCALAPPDATA 'GxpLowcodeReadonly\.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) {
    throw 'Runtime is missing. Run scripts\setup.ps1 first.'
}
& $pythonPath (Join-Path $pluginRoot 'scripts\configure_connection.py')
