param(
    [switch]$SkipBuild,
    [switch]$SkipUiSmokeTest
)

$ErrorActionPreference = "Stop"

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$appName = "DesktopFloatingWindow"
$distAppDir = Join-Path $scriptRoot "dist\$appName"
$releaseRoot = Join-Path $scriptRoot "release"
$bundleRoot = Join-Path $releaseRoot "${appName}_portable"
$bundleAppDir = Join-Path $bundleRoot $appName
$zipPath = Join-Path $releaseRoot "${appName}_portable.zip"

function Resolve-FullPath {
    param(
        [Parameter(Mandatory = $true)]
        [string]$PathValue
    )

    return [System.IO.Path]::GetFullPath($PathValue).TrimEnd("\")
}

function Remove-SafePath {
    param(
        [Parameter(Mandatory = $true)]
        [string]$PathValue,
        [Parameter(Mandatory = $true)]
        [string]$AllowedRoot
    )

    if (-not (Test-Path $PathValue)) {
        return
    }

    $resolvedPath = Resolve-FullPath -PathValue (Resolve-Path $PathValue).Path
    $resolvedRoot = Resolve-FullPath -PathValue $AllowedRoot
    if (-not $resolvedPath.StartsWith($resolvedRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to remove path outside release root: $resolvedPath"
    }

    Remove-Item -LiteralPath $resolvedPath -Recurse -Force
}

function Compress-WithRetry {
    param(
        [Parameter(Mandatory = $true)]
        [string]$SourcePattern,
        [Parameter(Mandatory = $true)]
        [string]$DestinationPath
    )

    $lastError = $null
    foreach ($attempt in 1..5) {
        try {
            Compress-Archive -Path $SourcePattern -DestinationPath $DestinationPath -Force
            return
        }
        catch {
            $lastError = $_
            if ($attempt -eq 5) {
                break
            }
            Start-Sleep -Seconds 2
        }
    }

    throw $lastError
}

if (-not $SkipBuild) {
    & (Join-Path $scriptRoot "build.ps1") -SkipUiSmokeTest:$SkipUiSmokeTest
}

if (-not (Test-Path (Join-Path $distAppDir "$appName.exe"))) {
    throw "Build output was not found: $distAppDir"
}

Remove-SafePath -PathValue $bundleRoot -AllowedRoot $releaseRoot
if (Test-Path $zipPath) {
    Remove-Item -LiteralPath $zipPath -Force
}

New-Item -ItemType Directory -Path $bundleRoot -Force | Out-Null
Copy-Item -Path $distAppDir -Destination $bundleAppDir -Recurse -Force
Copy-Item -Path (Join-Path $scriptRoot "install.ps1") -Destination (Join-Path $bundleRoot "install.ps1") -Force
Copy-Item -Path (Join-Path $scriptRoot "uninstall.ps1") -Destination (Join-Path $bundleRoot "uninstall.ps1") -Force
Copy-Item -Path (Join-Path $scriptRoot "RELEASE_README.md") -Destination (Join-Path $bundleRoot "README.md") -Force

Compress-WithRetry -SourcePattern (Join-Path $bundleRoot "*") -DestinationPath $zipPath

Write-Output "Release package OK"
Write-Output "Folder: $bundleRoot"
Write-Output "Zip: $zipPath"
