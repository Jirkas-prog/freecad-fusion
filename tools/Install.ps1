# Copies only the three add-ons; never downloads or replaces FreeCAD itself.
[CmdletBinding()]
param([string]$Profile = (Join-Path $env:APPDATA 'FreeCAD\v1-1'))
$ErrorActionPreference = 'Stop'
if (Get-Process -Name FreeCAD,FreeCADCmd -ErrorAction SilentlyContinue) {
    throw 'Save your documents and close FreeCAD before installation. No application was closed.'
}
$source = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$profilePath = [IO.Path]::GetFullPath($Profile)
$modPath = Join-Path $profilePath 'Mod'
$backup = Join-Path $profilePath ('FusionFlow-backups\' + (Get-Date -Format 'yyyyMMdd-HHmmss-fff'))
$packages = @{'FusionFlow' = 'FusionFlow'; 'freecad-fusion' = 'vendor\freecad-fusion'; 'OpenTheme' = 'vendor\OpenTheme'}
foreach ($name in $packages.Keys) {
    if (-not (Test-Path -LiteralPath (Join-Path $source ($packages[$name] + '\package.xml')))) {
        throw "Incomplete package: $name. Extract the whole download before running Install.cmd."
    }
}
# Refuse junctions/symlinks: never follow an existing link into another checkout.
foreach ($path in @($profilePath, $modPath) + @($packages.Keys | ForEach-Object { Join-Path $modPath $_ })) {
    if ((Test-Path -LiteralPath $path) -and ((Get-Item -LiteralPath $path).Attributes -band [IO.FileAttributes]::ReparsePoint)) {
        throw "Installation path is a link: $path. Use a normal profile directory."
    }
}
New-Item -ItemType Directory -Path $modPath,$backup -Force | Out-Null
foreach ($file in @('user.cfg','system.cfg')) {
    $path = Join-Path $profilePath $file
    if (Test-Path -LiteralPath $path) { Copy-Item -LiteralPath $path -Destination $backup }
}
foreach ($name in $packages.Keys) {
    $destination = Join-Path $modPath $name
    if (Test-Path -LiteralPath $destination) {
        Copy-Item -LiteralPath $destination -Destination $backup -Recurse
    }
    # Merge leaves unrelated files alone. The exact release is identified in package.xml.
    New-Item -ItemType Directory -Path $destination -Force | Out-Null
    Get-ChildItem -LiteralPath (Join-Path $source $packages[$name]) -Force |
        Where-Object { $_.Name -notin @('.git','.github','__pycache__','install.ps1','install.sh') -and $_.Extension -notin @('.pyc','.bak') } |
        ForEach-Object { Copy-Item -LiteralPath $_.FullName -Destination $destination -Recurse -Force }
}
Write-Host ''
Write-Host 'FusionFlow installed for FreeCAD 1.1.3 (Qt 6).' -ForegroundColor Green
Write-Host "Profile: $profilePath"
Write-Host "Backup:  $backup"
Write-Host 'Start FreeCAD. The ribbon and navigation activate automatically.'
Write-Host 'Restart once more after the first launch for the complete OpenDark theme.'
Write-Host 'See README.md for the shortcuts, limitations and removal instructions.'
