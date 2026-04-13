param(
    [string]$SourceDir = "",
    [string]$InstallDir = "",
    [string]$ShortcutDir = "",
    [string]$ShortcutArguments = "",
    [switch]$Force
)

$ErrorActionPreference = "Stop"

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$appName = "DesktopFloatingWindow"
$exeName = "$appName.exe"
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

if (-not $SourceDir) {
    $sourceCandidates = @(
        (Join-Path $scriptRoot "dist\$appName"),
        (Join-Path $scriptRoot $appName)
    )
    $SourceDir = $sourceCandidates |
        Where-Object { Test-Path (Join-Path $_ $exeName) } |
        Select-Object -First 1
}

if (-not $SourceDir) {
    throw "Could not find a build output folder. Expected '$scriptRoot\dist\$appName' or pass -SourceDir explicitly."
}

$resolvedSourceDir = Resolve-FullPath -PathValue (Resolve-Path $SourceDir).Path
$sourceExePath = Join-Path $resolvedSourceDir $exeName
if (-not (Test-Path $sourceExePath)) {
    throw "EXE was not found in source directory: $sourceExePath"
}

if (-not $InstallDir) {
    $InstallDir = Join-Path $env:LOCALAPPDATA $appName
}
$resolvedInstallDir = Assert-SafeDirectory -PathValue $InstallDir

if (-not $ShortcutDir) {
    $ShortcutDir = [Environment]::GetFolderPath("Desktop")
}
$resolvedShortcutDir = Assert-SafeDirectory -PathValue $ShortcutDir
$shortcutPath = Join-Path $resolvedShortcutDir $shortcutName

if ((Test-Path $resolvedInstallDir) -and -not $Force) {
    throw "Install directory already exists: $resolvedInstallDir. Re-run with -Force to replace it."
}

if (Test-Path $resolvedInstallDir) {
    Remove-Item -LiteralPath $resolvedInstallDir -Recurse -Force
}

New-Item -ItemType Directory -Path $resolvedInstallDir -Force | Out-Null
Copy-Item -Path (Join-Path $resolvedSourceDir "*") -Destination $resolvedInstallDir -Recurse -Force

New-Item -ItemType Directory -Path $resolvedShortcutDir -Force | Out-Null
$installedExePath = Join-Path $resolvedInstallDir $exeName

$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $installedExePath
$shortcut.Arguments = $ShortcutArguments
$shortcut.WorkingDirectory = $resolvedInstallDir
$shortcut.IconLocation = "$installedExePath,0"
$shortcut.Description = "Desktop Floating Window launch shortcut"
$shortcut.Save()

Write-Output "Install OK"
Write-Output "Source: $resolvedSourceDir"
Write-Output "InstallDir: $resolvedInstallDir"
Write-Output "Shortcut: $shortcutPath"
