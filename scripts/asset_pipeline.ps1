$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$pythonScript = Join-Path $scriptDir 'asset_pipeline.py'

& python $pythonScript @args
exit $LASTEXITCODE
