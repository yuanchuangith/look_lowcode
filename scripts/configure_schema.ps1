$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$runtime = if ($env:GXP_LOWCODE_RUNTIME_ROOT) { $env:GXP_LOWCODE_RUNTIME_ROOT } else { Join-Path $env:LOCALAPPDATA 'GxpLowcodeReadonly' }
$python = Join-Path $runtime '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) { throw "Look runtime is missing. Run scripts/setup.ps1 first." }
& $python (Join-Path $root 'scripts\configure_schema.py') @args
exit $LASTEXITCODE

