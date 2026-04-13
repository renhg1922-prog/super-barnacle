param(
    [string]$InstallDir = "",
    [string]$ShortcutDir = ""
)

$ErrorActionPreference = "Stop"

$appName = "DesktopFloatingWindow"
$shortcutName = "$appName.lnk"

function Resolve-FullPath {
    param(
        [Parameter(Mandatory = $true)]
        [string]$PathValue
    )

    return [System.IO.Path]::GetFullPath($PathValue).TrimEnd("\")
}

function Assert-SafeDirectory {
    param(
        [Parameter(Mandatory = $true)]
        [string]$PathValue
    )

    $resolved = Resolve-FullPath -PathValue $PathValue
    $root = [System.IO.Path]::GetPathRoot($resolved)
    if ([string]::IsNullOrWhiteSpace($resolved) -or $resolved -eq $root) {
        throw "Refusing to use an unsafe directory path: $PathValue"
    }

    return $resolved
}

if (-not $InstallDir) {
    $InstallDir = Join-Path $env:LOCALAPPDATA $appName
}
if (-not $ShortcutDir) {
    $ShortcutDir = [Environment]::GetFolderPath("Desktop")
}

$resolvedInstallDir = Assert-SafeDirectory -PathValue $InstallDir
$resolvedShortcutDir = Assert-SafeDirectory -PathValue $ShortcutDir
$shortcutPath = Join-Path $resolvedShortcutDir $shortcutName

if (Test-Path $shortcutPath) {
    Remove-Item -LiteralPath $shortcutPath -Force
}

if (Test-Path $resolvedInstallDir) {
    Remove-Item -LiteralPath $resolvedInstallDir -Recurse -Force
}

Write-Output "Uninstall OK"
Write-Output "InstallDir: $resolvedInstallDir"
Write-Output "Shortcut: $shortcutPath"
