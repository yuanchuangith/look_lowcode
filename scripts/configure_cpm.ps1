[CmdletBinding()]
param(
    [string]$PlatformUrl = '',
    [string]$Account = ''
)

$ErrorActionPreference = 'Stop'
$pluginRoot = Split-Path -Parent $PSScriptRoot
$runtimeRoot = Join-Path $env:LOCALAPPDATA 'GxpLowcodeReadonly'
$pythonPath = Join-Path $runtimeRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) {
    throw 'Runtime is missing. Run scripts\setup.ps1 first.'
}
$package = Get-Content -LiteralPath (Join-Path $pluginRoot 'vendor\cpm-cli\package.json') -Raw | ConvertFrom-Json
$cliPath = Join-Path $runtimeRoot (Join-Path "cpm-cli\$($package.version)" 'dist\cli.js')
if (-not (Test-Path -LiteralPath $cliPath)) {
    throw 'CPM CLI runtime is missing. Run scripts\setup.ps1 first.'
}
$nodePath = (Get-Command node.exe -ErrorAction Stop).Source
$argsList = @(
    (Join-Path $pluginRoot 'scripts\configure_cpm.py'),
    '--node-path', $nodePath,
    '--cli-path', $cliPath
)
if ($PlatformUrl) { $argsList += @('--url', $PlatformUrl) }
if ($Account) { $argsList += @('--account', $Account) }
& $pythonPath @argsList
