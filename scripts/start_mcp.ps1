[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$pluginRoot = Split-Path -Parent $PSScriptRoot
$pythonPath = Join-Path $env:LOCALAPPDATA 'GxpLowcodeReadonly\.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) {
    throw 'GXP read-only MCP runtime is missing. Run scripts\setup.ps1 first.'
}
& $pythonPath (Join-Path $pluginRoot 'mcp\server.py')
