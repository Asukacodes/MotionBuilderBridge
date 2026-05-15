param(
    [ValidateSet("Claude", "Codex", "Both")]
    [string]$Target = "Both",

    [string]$BridgeHome = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path,

    [switch]$Force
)

$ErrorActionPreference = "Stop"

function Copy-Skill {
    param(
        [string]$DestinationRoot,
        [string]$BridgeHome
    )

    $src = Join-Path $BridgeHome ".claude\skills\motionbuilder-bridge"
    if (-not (Test-Path -LiteralPath $src)) {
        throw "Skill source not found: $src"
    }

    $dst = Join-Path $DestinationRoot "motionbuilder-bridge"
    if ((Test-Path -LiteralPath $dst) -and -not $Force) {
        Write-Host "Removing existing skill: $dst"
        Remove-Item -LiteralPath $dst -Recurse -Force
    } elseif (Test-Path -LiteralPath $dst) {
        Remove-Item -LiteralPath $dst -Recurse -Force
    }

    New-Item -ItemType Directory -Force -Path $DestinationRoot | Out-Null
    Copy-Item -LiteralPath $src -Destination $dst -Recurse -Force

    $homeFile = Join-Path $dst "bridge_home.txt"
    Set-Content -LiteralPath $homeFile -Value $BridgeHome -Encoding UTF8
    Write-Host "Installed skill: $dst"
}

$BridgeHome = (Resolve-Path -LiteralPath $BridgeHome).Path
if (-not (Test-Path -LiteralPath (Join-Path $BridgeHome "scripts\bridge.py"))) {
    throw "BridgeHome does not look like MotionBuilderBridge: $BridgeHome"
}

if ($Target -in @("Claude", "Both")) {
    Copy-Skill -DestinationRoot (Join-Path $env:USERPROFILE ".claude\skills") -BridgeHome $BridgeHome
}

if ($Target -in @("Codex", "Both")) {
    Copy-Skill -DestinationRoot (Join-Path $env:USERPROFILE ".codex\skills") -BridgeHome $BridgeHome
}

[Environment]::SetEnvironmentVariable("MOTIONBUILDER_BRIDGE_HOME", $BridgeHome, "User")
Write-Host "Set user environment MOTIONBUILDER_BRIDGE_HOME=$BridgeHome"
Write-Host "Restart Claude/Codex after installation so they reload skills and environment."
