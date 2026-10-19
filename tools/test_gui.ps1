param([Parameter(Mandatory=$true)][string]$FreeCAD)
$ErrorActionPreference='Stop'
$source=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$profile=Join-Path ([IO.Path]::GetTempPath()) ('fusionflow-gui-'+[guid]::NewGuid().ToString('N'))
$output=Join-Path $source 'test-output'
New-Item -ItemType Directory -Path "$profile\Mod","$profile\temp",$output -Force | Out-Null
Copy-Item -LiteralPath "$source\FusionFlow" -Destination "$profile\Mod" -Recurse
Copy-Item -LiteralPath "$source\vendor\freecad-fusion" -Destination "$profile\Mod" -Recurse
Copy-Item -LiteralPath "$source\vendor\OpenTheme" -Destination "$profile\Mod" -Recurse
$env:FREECAD_USER_HOME=$profile
$env:FUSIONFLOW_GUI_TEST='1'
$env:FUSIONFLOW_SOURCE=$source
$env:FUSIONFLOW_TEST_OUTPUT=$output
$env:TEMP="$profile\temp"
$env:TMP=$env:TEMP
$started=Get-Date
$process=Start-Process -FilePath $FreeCAD -ArgumentList @('--write-log','--log-file',"`"$output\gui.log`"","`"$source\tests\gui_smoke.FCMacro`"") -WindowStyle Hidden -PassThru
if (-not $process.WaitForExit(90000)) { throw "Test timed out; isolated process PID $($process.Id). User FreeCAD was not touched." }
$report=Join-Path $output 'gui.json'
if (-not (Test-Path -LiteralPath $report) -or (Get-Item -LiteralPath $report).LastWriteTime -lt $started) { throw 'No fresh GUI result' }
$result=Get-Content -LiteralPath $report -Raw | ConvertFrom-Json
$result | ConvertTo-Json
if (-not $result.passed) { throw 'GUI smoke test failed' }
