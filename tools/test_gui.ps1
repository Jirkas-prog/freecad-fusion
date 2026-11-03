param([Parameter(Mandatory=$true)][string]$FreeCAD,
      [ValidateSet('en','cs')][string]$Language='en',
      [ValidateSet('smoke','language')][string]$Suite='smoke')
$ErrorActionPreference='Stop'
$source=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$profile=Join-Path ([IO.Path]::GetTempPath()) ('fusionflow-gui-'+[guid]::NewGuid().ToString('N'))
$output=Join-Path $source "test-output\$Suite-$Language"
New-Item -ItemType Directory -Path "$profile\Mod","$profile\temp",$output -Force | Out-Null
Copy-Item -LiteralPath "$source\FusionFlow" -Destination "$profile\Mod" -Recurse
Copy-Item -LiteralPath "$source\vendor\freecad-fusion" -Destination "$profile\Mod" -Recurse
Copy-Item -LiteralPath "$source\vendor\OpenTheme" -Destination "$profile\Mod" -Recurse
$env:FREECAD_USER_HOME=$profile
$env:FUSIONFLOW_GUI_TEST='1'
$env:FUSIONFLOW_SOURCE=$source
$env:FUSIONFLOW_TEST_OUTPUT=$output
$env:FUSIONFLOW_TEST_LANGUAGE=$Language
$env:TEMP="$profile\temp"
$env:TMP=$env:TEMP
# Set the language before InitGui imports the session's fixed message catalog.
$python=Join-Path (Split-Path -Parent $FreeCAD) 'python.exe'
& $python -c "import os, FreeCAD as A; A.ParamGet('User parameter:BaseApp/Preferences/General').SetString('Language', 'Czech' if os.environ['FUSIONFLOW_TEST_LANGUAGE']=='cs' else 'English'); A.saveParameter()"
if ($LASTEXITCODE -ne 0) { throw 'Could not initialize isolated language preference' }
$started=Get-Date
$process=Start-Process -FilePath $FreeCAD -ArgumentList @('--write-log','--log-file',"`"$output\gui.log`"","`"$source\tests\gui_$Suite.FCMacro`"") -WindowStyle Hidden -PassThru
if (-not $process.WaitForExit(90000)) { throw "Test timed out; isolated process PID $($process.Id). User FreeCAD was not touched." }
$report=Join-Path $output 'gui.json'
if (-not (Test-Path -LiteralPath $report) -or (Get-Item -LiteralPath $report).LastWriteTime -lt $started) { throw 'No fresh GUI result' }
$result=Get-Content -LiteralPath $report -Raw | ConvertFrom-Json
$result | ConvertTo-Json
if (-not $result.passed) { throw 'GUI smoke test failed' }
