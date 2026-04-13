$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$distRoot = Join-Path $projectRoot "dist"
$buildRoot = Join-Path $projectRoot "build"
$verificationRoot = Join-Path $projectRoot "relocation_check"
$appName = "DesktopFloatingWindow"

function Resolve-FullPath {
    param(
        [Parameter(Mandatory = $true)]
        [string]$PathValue
    )

    return [System.IO.Path]::GetFullPath($PathValue).TrimEnd("\")
}

function Remove-SafeDirectory {
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
        throw "Refusing to remove path outside verification root: $resolvedPath"
    }

    Remove-Item -LiteralPath $resolvedPath -Recurse -Force
}

Push-Location $projectRoot
try {
    python -m PyInstaller `
        --noconfirm `
        --clean `
        --windowed `
        --onedir `
        --name $appName `
        --hidden-import pythoncom `
        --hidden-import pywintypes `
        --hidden-import win32api `
        --hidden-import win32con `
        --hidden-import win32gui `
        --hidden-import win32com `
        --hidden-import win32com.client `
        --distpath $distRoot `
        --workpath $buildRoot `
        app.py

    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }

    $exePath = Join-Path $distRoot "$appName\$appName.exe"
    if (-not (Test-Path $exePath)) {
        throw "Build finished but EXE was not found: $exePath"
    }

    & $exePath --smoke-test | Out-Null

    $reportPath = Join-Path $distRoot "$appName\portable_runtime_report.json"
    if (-not (Test-Path $reportPath)) {
        throw "Smoke test did not create the runtime report: $reportPath"
    }

    $uiSmoke = Start-Process -FilePath $exePath -ArgumentList '--ui-smoke-test' -PassThru -Wait
    if ($uiSmoke.ExitCode -ne 0) {
        throw "UI smoke test failed with exit code $($uiSmoke.ExitCode)"
    }

    $installScript = Join-Path $projectRoot "install.ps1"
    if (-not (Test-Path $installScript)) {
        throw "Install script was not found: $installScript"
    }

    $installRoot = Join-Path $verificationRoot "installed_app"
    $shortcutRoot = Join-Path $verificationRoot "desktop_shortcut"
    Remove-SafeDirectory -PathValue $installRoot -AllowedRoot $verificationRoot
    Remove-SafeDirectory -PathValue $shortcutRoot -AllowedRoot $verificationRoot

    & $installScript `
        -SourceDir (Join-Path $distRoot $appName) `
        -InstallDir $installRoot `
        -ShortcutDir $shortcutRoot `
        -ShortcutArguments '--smoke-test' `
        -Force | Out-Null

    $shortcutPath = Join-Path $shortcutRoot "$appName.lnk"
    if (-not (Test-Path $shortcutPath)) {
        throw "Install validation did not create the shortcut: $shortcutPath"
    }

    $installedReportPath = Join-Path $installRoot "portable_runtime_report.json"
    if (Test-Path $installedReportPath) {
        Remove-Item -LiteralPath $installedReportPath -Force
    }

    Start-Process -FilePath $shortcutPath | Out-Null
    $deadline = (Get-Date).AddSeconds(10)
    while (-not (Test-Path $installedReportPath) -and (Get-Date) -lt $deadline) {
        Start-Sleep -Milliseconds 250
    }

    if (-not (Test-Path $installedReportPath)) {
        throw "Shortcut launch validation did not produce a runtime report: $installedReportPath"
    }

    $resolvedInstallRoot = Resolve-FullPath -PathValue $installRoot
    $installedReport = Get-Content $installedReportPath -Raw -Encoding UTF8 | ConvertFrom-Json
    if ((Resolve-FullPath -PathValue $installedReport.app_dir) -ne $resolvedInstallRoot) {
        throw "Shortcut launch used the wrong app directory: $($installedReport.app_dir)"
    }
    if ((Resolve-FullPath -PathValue $installedReport.settings_path) -ne (Join-Path $resolvedInstallRoot "floating_window_settings.json")) {
        throw "Shortcut launch used the wrong settings path: $($installedReport.settings_path)"
    }

    Write-Output "Build OK"
    Write-Output "EXE: $exePath"
    Write-Output "Runtime report: $reportPath"
    Write-Output "Shortcut validation: $shortcutPath"
}
finally {
    Pop-Location
}
