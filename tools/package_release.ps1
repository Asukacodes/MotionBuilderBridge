param(
    [string]$BridgeHome = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path,
    [string]$OutDir = (Join-Path (Resolve-Path (Join-Path $PSScriptRoot "..")).Path "dist")
)

$ErrorActionPreference = "Stop"

$BridgeHome = (Resolve-Path -LiteralPath $BridgeHome).Path
$OutDir = [System.IO.Path]::GetFullPath($OutDir)
$stage = Join-Path $OutDir "MotionBuilderBridge"
$zip = Join-Path $OutDir "MotionBuilderBridge.zip"

if (Test-Path -LiteralPath $stage) {
    Remove-Item -LiteralPath $stage -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $stage | Out-Null

$allowedRoots = @(".claude", "docs", "py", "scripts", "tools")
$allowedFiles = @("README.md", "AGENTS.md", "CLAUDE.md")
$skipDirNames = @("__pycache__", "dist", ".git")
$skipFilePatterns = @("*.pyc", "*.pyo", "bridge_home.txt", "fifo_req.txt", "mb_test_write.txt")

function Should-SkipFile {
    param([System.IO.FileInfo]$File)
    foreach ($pattern in $skipFilePatterns) {
        if ($File.Name -like $pattern) {
            return $true
        }
    }
    foreach ($part in $File.FullName.Substring($BridgeHome.Length).TrimStart('\', '/') -split '[\\/]') {
        if ($skipDirNames -contains $part) {
            return $true
        }
    }
    return $false
}

foreach ($rootName in $allowedRoots) {
    $rootPath = Join-Path $BridgeHome $rootName
    if (-not (Test-Path -LiteralPath $rootPath)) {
        continue
    }
    Get-ChildItem -LiteralPath $rootPath -Recurse -File -Force | ForEach-Object {
        if (Should-SkipFile $_) {
            return
        }
        $rel = $_.FullName.Substring($BridgeHome.Length).TrimStart('\', '/')
        $target = Join-Path $stage $rel
        New-Item -ItemType Directory -Force -Path (Split-Path -Parent $target) | Out-Null
        Copy-Item -LiteralPath $_.FullName -Destination $target -Force
    }
}

foreach ($fileName in $allowedFiles) {
    $src = Join-Path $BridgeHome $fileName
    if (Test-Path -LiteralPath $src) {
        Copy-Item -LiteralPath $src -Destination (Join-Path $stage $fileName) -Force
    }
}

$fileCount = (Get-ChildItem -LiteralPath $stage -Recurse -File -Force | Measure-Object).Count
if ($fileCount -lt 10) {
    throw "Package staging looks incomplete: only $fileCount files copied to $stage"
}

if (Test-Path -LiteralPath $zip) {
    Remove-Item -LiteralPath $zip -Force
}
Compress-Archive -LiteralPath $stage -DestinationPath $zip -Force

Write-Host "Created package: $zip"
Write-Host "Staged files: $fileCount"
Write-Host "Install agent skill after extracting:"
Write-Host "  powershell -ExecutionPolicy Bypass -File tools\install_agent_skill.ps1 -Target Both"
Write-Host "Install MotionBuilder startup loader if desired:"
Write-Host "  powershell -ExecutionPolicy Bypass -File tools\install_mobu_startup.ps1 -AutoStartBridge -OpenPanel"
