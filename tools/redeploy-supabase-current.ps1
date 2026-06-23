param(
    [string]$ProjectRef = "ofogstpjheigpnsmnlxn"
)

$ErrorActionPreference = "Stop"
$RootDir = Split-Path -Parent $PSScriptRoot
$CliScript = Join-Path $RootDir "tools\run-supabase-cli.mjs"
$RedeployLogPath = Join-Path $RootDir "config\supabase-redeploy-last.log"

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

function New-CallbackSecret {
    $bytes = New-Object byte[] 32
    $rng = [Security.Cryptography.RandomNumberGenerator]::Create()
    try {
        $rng.GetBytes($bytes)
        return [Convert]::ToBase64String($bytes)
    } finally {
        $rng.Dispose()
    }
}

function New-HmacSha256Hex {
    param(
        [string]$Secret,
        [string]$Message
    )

    $keyBytes = [Text.Encoding]::UTF8.GetBytes($Secret)
    $messageBytes = [Text.Encoding]::UTF8.GetBytes($Message)
    $hmac = [Security.Cryptography.HMACSHA256]::new($keyBytes)
    try {
        $hash = $hmac.ComputeHash($messageBytes)
        return -join ($hash | ForEach-Object { $_.ToString("x2") })
    } finally {
        $hmac.Dispose()
    }
}

function Invoke-CallbackAcceptanceCheck {
    param(
        [string]$ProjectRef,
        [string]$CallbackSecret
    )

    $version = 1
    $issuedAt = [DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds()
    $nonce = [Guid]::NewGuid().ToString("N")
    $signedText = "$version.$issuedAt.$nonce"
    $signature = New-HmacSha256Hex -Secret $CallbackSecret -Message $signedText
    $metadata = @{
        v = $version
        ts = $issuedAt
        nonce = $nonce
        sig = $signature
        label = "pre-submit callback acceptance audit"
    } | ConvertTo-Json -Compress
    $payload = @{
        startTime = $issuedAt
        shortCode = "CALLBACK-AUDIT"
        metaData = $metadata
        gameId = 1234567890
        gameName = "pre-submit-callback-audit"
        gameType = "Practice"
        gameMap = 11
        gameMode = "CLASSIC"
        region = "KR"
    } | ConvertTo-Json -Depth 10 -Compress

    $callbackUrl = "https://$ProjectRef.supabase.co/functions/v1/riot-callback"
    $response = Invoke-WebRequest `
        -UseBasicParsing `
        -Method Post `
        -Uri $callbackUrl `
        -ContentType "application/json" `
        -Body $payload
    if ($response.StatusCode -ne 200) {
        throw "Callback acceptance check failed with HTTP $($response.StatusCode)"
    }
    Write-Host "Valid callback acceptance returned HTTP 200." -ForegroundColor Green
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
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $RedeployLogPath) | Out-Null
Start-Transcript -Path $RedeployLogPath -Force | Out-Null

Write-Host "Supabase Edge Function redeploy for LOL Tournament Code Creator" -ForegroundColor Green
Write-Host "Project ref: $ProjectRef"
Write-Host "This updates RIOT_CALLBACK_SECRET and redeploys riot-tournament + riot-callback."
Write-Host "Existing RIOT_API_KEY, RIOT_CALLBACK_URL, and ALLOWED_OPERATOR_EMAILS are not changed."
Write-Host "Paste the Supabase account access token only into this PowerShell window."

$supabaseToken = Read-SecretValue "Supabase account access token"
$env:SUPABASE_ACCESS_TOKEN = $supabaseToken
$callbackSecret = New-CallbackSecret
$tempSecrets = Join-Path ([IO.Path]::GetTempPath()) ("lol-tournament-callback-secret-" + [Guid]::NewGuid().ToString("N") + ".env")

try {
    "RIOT_CALLBACK_SECRET=$callbackSecret" | Set-Content -LiteralPath $tempSecrets -Encoding UTF8

    Invoke-CheckedCommand "Upload RIOT_CALLBACK_SECRET" @(
        "node",
        $CliScript,
        "secrets",
        "set",
        "--env-file",
        $tempSecrets,
        "--project-ref",
        $ProjectRef
    )

    Invoke-CheckedCommand "Deploy riot-tournament" @(
        "node",
        $CliScript,
        "functions",
        "deploy",
        "riot-tournament",
        "--use-api",
        "--project-ref",
        $ProjectRef
    )

    Invoke-CheckedCommand "Deploy riot-callback" @(
        "node",
        $CliScript,
        "functions",
        "deploy",
        "riot-callback",
        "--use-api",
        "--project-ref",
        $ProjectRef
    )

    Invoke-CheckedCommand "List deployed functions" @(
        "node",
        $CliScript,
        "functions",
        "list",
        "--project-ref",
        $ProjectRef
    )

    Invoke-CheckedCommand "List configured secret names" @(
        "node",
        $CliScript,
        "secrets",
        "list",
        "--project-ref",
        $ProjectRef
    )

    Write-Host ""
    Write-Host "== Verify signed Riot callback acceptance ==" -ForegroundColor Cyan
    Invoke-CallbackAcceptanceCheck -ProjectRef $ProjectRef -CallbackSecret $callbackSecret

    Write-Host ""
    Write-Host "Supabase redeploy completed." -ForegroundColor Green
} finally {
    Remove-Item -LiteralPath $tempSecrets -Force -ErrorAction SilentlyContinue
    Remove-Item Env:\SUPABASE_ACCESS_TOKEN -ErrorAction SilentlyContinue
    Stop-Transcript | Out-Null
}

Read-Host "Press Enter to close"
