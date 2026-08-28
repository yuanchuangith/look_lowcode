[CmdletBinding()]
param(
    [Alias('PageIdentifier')]
    [string]$Page = '',
    [switch]$IfStale,
    [switch]$Json
)

$ErrorActionPreference = 'Stop'
$pluginRoot = Split-Path -Parent $PSScriptRoot
$pythonPath = Join-Path $env:LOCALAPPDATA 'GxpLowcodeReadonly\.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) {
    throw 'Runtime is missing. Run scripts\setup.ps1 first.'
}

$argsList = @(Join-Path $pluginRoot 'scripts\pull_cpm.py')
if ($Page) { $argsList += @('--page', $Page) }
if ($IfStale) { $argsList += '--if-stale' }
if ($Json) { $argsList += '--json' }
& $pythonPath @argsList
exit $LASTEXITCODE
