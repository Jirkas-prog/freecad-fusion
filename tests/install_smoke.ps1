$ErrorActionPreference='Stop'
$source=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$profile=Join-Path ([IO.Path]::GetTempPath()) ('fusionflow-install-'+[guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path "$profile\Mod\FusionFlow" -Force | Out-Null
Set-Content -LiteralPath "$profile\user.cfg" -Value '<test>original settings</test>'
Set-Content -LiteralPath "$profile\Mod\FusionFlow\previous.txt" -Value 'previous version'
$before=(Get-FileHash -LiteralPath "$profile\user.cfg").Hash
# Simulate a closed desktop; the actual installation target is this isolated temp profile.
function Get-Process { param($Name,$ErrorAction) return @() }
& "$source\tools\Install.ps1" -Profile $profile
if ((Get-FileHash -LiteralPath "$profile\user.cfg").Hash -ne $before) { throw 'Installer changed preferences' }
$backup=Get-ChildItem -LiteralPath "$profile\FusionFlow-backups" -Directory | Select-Object -First 1
if ((Get-FileHash -LiteralPath (Join-Path $backup.FullName 'user.cfg')).Hash -ne $before) { throw 'Backup differs' }
if (-not (Test-Path -LiteralPath (Join-Path $backup.FullName 'FusionFlow\previous.txt'))) { throw 'Previous add-on not backed up' }
foreach ($name in @('FusionFlow','freecad-fusion','OpenTheme')) {
    if (-not (Test-Path -LiteralPath "$profile\Mod\$name\package.xml")) { throw "Missing package: $name" }
}
Write-Host 'PASS: three add-ons installed, old add-on backed up, preferences preserved.'
