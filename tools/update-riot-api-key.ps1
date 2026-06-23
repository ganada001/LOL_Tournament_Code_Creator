param(
    [string]$ProjectRef = ""
)

$ErrorActionPreference = "Stop"
$RootDir = Split-Path -Parent $PSScriptRoot
$SummaryPath = Join-Path $RootDir "config\supabase-deployment.json"
$ClientSettingsPath = Join-Path $RootDir "client_settings.py"
$CliScript = Join-Path $RootDir "tools\run-supabase-cli.mjs"
$TempSecrets = Join-Path ([IO.Path]::GetTempPath()) ("lol-tournament-riot-key-" + [Guid]::NewGuid().ToString("N") + ".env")

function Read-SecretValue {
    param([string]$Prompt)

    do {
        $secure = Read-Host $Prompt -AsSecureString
        $ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
        try {
            $value = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr)
        } finally {
            [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr)
        }
    } while ([string]::IsNullOrWhiteSpace($value))
    return $value
}

function Invoke-CheckedCommand {
    param([string]$Label, [string[]]$Command)

    Write-Host ""
    Write-Host "== $Label ==" -ForegroundColor Cyan
    $arguments = @()
    if ($Command.Length -gt 1) {
        $arguments = $Command[1..($Command.Length - 1)]
    }
    & $Command[0] @arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$Label failed with exit code $LASTEXITCODE"
    }
}

Set-Location $RootDir

if (-not $ProjectRef -and (Test-Path $SummaryPath)) {
    $summary = Get-Content -Raw -LiteralPath $SummaryPath | ConvertFrom-Json
    $ProjectRef = [string]$summary.project_ref
}

if (-not $ProjectRef -and (Test-Path $ClientSettingsPath)) {
    $settingsText = Get-Content -Raw -LiteralPath $ClientSettingsPath
    $match = [regex]::Match($settingsText, 'SUPABASE_PROJECT_URL\s*=\s*"https://([^.]+)\.supabase\.co"')
    if ($match.Success) {
        $ProjectRef = $match.Groups[1].Value
    }
}

if (-not $ProjectRef) {
    $ProjectRef = Read-Host "Supabase project ref"
}

$supabaseToken = Read-SecretValue "Supabase account access token"
$riotApiKey = Read-SecretValue "New Riot API key (development before approval; production after approval)"
if (-not $riotApiKey.StartsWith("RGAPI-")) {
    throw "Riot API key must start with RGAPI-."
}

try {
    "RIOT_API_KEY=$riotApiKey" | Set-Content -LiteralPath $TempSecrets -Encoding UTF8
    $env:SUPABASE_ACCESS_TOKEN = $supabaseToken

    $node = (Get-Command node.exe -ErrorAction Stop).Source
    Invoke-CheckedCommand "Upload Riot API key secret" @(
        $node,
        $CliScript,
        "secrets",
        "set",
        "--env-file",
        $TempSecrets,
        "--project-ref",
        $ProjectRef
    )
    Write-Host ""
    Write-Host "Riot API key secret updated for Supabase project $ProjectRef." -ForegroundColor Green
} finally {
    Remove-Item -LiteralPath $TempSecrets -Force -ErrorAction SilentlyContinue
    Remove-Item Env:\SUPABASE_ACCESS_TOKEN -ErrorAction SilentlyContinue
}

Read-Host "Press Enter to close"
