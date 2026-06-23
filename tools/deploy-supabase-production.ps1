param(
    [string]$DefaultOrgId = "omohzqounukstnnnyyme",
    [string]$DefaultProjectName = "lol-tournament-code-creator",
    [string]$DefaultRegion = "ap-northeast-2",
    [switch]$SkipPredeploy
)

$ErrorActionPreference = "Stop"

$RootDir = Split-Path -Parent $PSScriptRoot
$CliScript = Join-Path $RootDir "tools\run-supabase-cli.mjs"
$JsonCliScript = Join-Path $RootDir "tools\supabase-json.mjs"
$SummaryPath = Join-Path $RootDir "config\supabase-deployment.json"
$DeployLogPath = Join-Path $RootDir "config\supabase-deploy-last.log"

function Sanitize-LogText {
    param([string]$Text)

    return ($Text `
        -replace 'RGAPI-[A-Za-z0-9_-]+', 'RGAPI-***' `
        -replace 'sbp_[A-Za-z0-9_.-]+', 'sbp_***' `
        -replace 'sb_secret_[A-Za-z0-9_.-]+', 'sb_secret_***' `
        -replace 'sb_publishable_[A-Za-z0-9_.-]+', 'sb_publishable_***' `
        -replace 'eyJ[A-Za-z0-9_.-]{20,}', 'eyJ***')
}

function Write-DeployLog {
    param([string]$Message)

    $line = "$(Get-Date -Format o) $(Sanitize-LogText $Message)"
    Add-Content -LiteralPath $DeployLogPath -Value $line -Encoding UTF8
}

New-Item -ItemType Directory -Force -Path (Split-Path -Parent $DeployLogPath) | Out-Null
Set-Content -LiteralPath $DeployLogPath -Value "$(Get-Date -Format o) Supabase approval-ready deploy started." -Encoding UTF8

trap {
    $message = Sanitize-LogText ([string]$_)
    Write-DeployLog "ERROR: $message"
    Write-Host ""
    Write-Host "Deployment failed:" -ForegroundColor Red
    Write-Host $message -ForegroundColor Red
    Write-Host "Sanitized log: $DeployLogPath" -ForegroundColor Yellow
    Read-Host "Press Enter to close"
    exit 1
}

function Read-RequiredValue {
    param([string]$Prompt, [string]$DefaultValue = "")

    if ($DefaultValue) {
        $value = Read-Host "$Prompt [$DefaultValue]"
        if ([string]::IsNullOrWhiteSpace($value)) {
            return $DefaultValue
        }
        return $value.Trim()
    }

    do {
        $value = Read-Host $Prompt
    } while ([string]::IsNullOrWhiteSpace($value))
    return $value.Trim()
}

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

function Invoke-CheckedCommand {
    param([string]$Label, [string[]]$Command)

    Write-Host ""
    Write-Host "== $Label ==" -ForegroundColor Cyan
    Write-DeployLog "STEP: $Label"
    $arguments = @()
    if ($Command.Length -gt 1) {
        $arguments = $Command[1..($Command.Length - 1)]
    }
    & $Command[0] @arguments
    if ($LASTEXITCODE -ne 0) {
        Write-DeployLog "FAILED: $Label exit code $LASTEXITCODE"
        throw "$Label failed with exit code $LASTEXITCODE"
    }
    Write-DeployLog "OK: $Label"
}

function Invoke-SupabaseCli {
    param([string]$Label, [string[]]$Arguments)

    $node = (Get-Command node.exe -ErrorAction Stop).Source
    $command = @($node, $CliScript) + $Arguments
    Invoke-CheckedCommand $Label $command
}

function Invoke-SupabaseCliJson {
    param([string]$Label, [string[]]$Arguments)

    Write-Host ""
    Write-Host "== $Label ==" -ForegroundColor Cyan
    Write-DeployLog "STEP: $Label"
    $node = (Get-Command node.exe -ErrorAction Stop).Source
    $previousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $output = & $node $JsonCliScript @Arguments 2>&1
        $exitCode = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $previousErrorActionPreference
    }
    if ($exitCode -ne 0) {
        $text = ($output | Out-String).Trim()
        if ($text) {
            Write-Host $text
            Write-DeployLog "OUTPUT: $text"
        }
        Write-DeployLog "FAILED: $Label exit code $exitCode"
        throw "$Label failed with exit code $exitCode"
    }

    $json = ($output | Out-String).Trim()
    if (-not $json) {
        throw "$Label returned an empty response"
    }

    try {
        return $json | ConvertFrom-Json
    } catch {
        Write-Host $json
        Write-DeployLog "FAILED JSON PARSE: $Label output=$(Sanitize-LogText $json)"
        throw "Unable to parse JSON returned by $Label"
    }
    Write-DeployLog "OK: $Label"
}

function Invoke-SupabaseManagementApi {
    param(
        [string]$Label,
        [string]$Method,
        [string]$Path,
        $Body = $null
    )

    Write-Host ""
    Write-Host "== $Label ==" -ForegroundColor Cyan
    Write-DeployLog "STEP: $Label"

    $headers = @{
        "Authorization" = "Bearer $script:SupabaseAccountToken"
        "Content-Type" = "application/json"
    }
    $uri = "https://api.supabase.com/v1$Path"

    try {
        if ($null -eq $Body) {
            $result = Invoke-RestMethod -Method $Method -Uri $uri -Headers $headers
        } else {
            $jsonBody = $Body | ConvertTo-Json -Depth 10 -Compress
            $result = Invoke-RestMethod -Method $Method -Uri $uri -Headers $headers -Body $jsonBody
        }
        Write-DeployLog "OK: $Label"
        return $result
    } catch {
        $message = $_.Exception.Message
        if ($_.Exception.Response -and $_.Exception.Response.GetResponseStream()) {
            try {
                $reader = New-Object IO.StreamReader($_.Exception.Response.GetResponseStream())
                $responseBody = $reader.ReadToEnd()
                if ($responseBody) {
                    $message = "$message $responseBody"
                }
            } catch {
                $message = $_.Exception.Message
            }
        }
        Write-DeployLog "FAILED: $Label $message"
        throw "$Label failed: $(Sanitize-LogText $message)"
    }
}

function Get-Items {
    param($Value)

    if ($null -eq $Value) {
        return @()
    }
    if ($Value -is [array]) {
        return @($Value)
    }
    foreach ($propertyName in @("projects", "organizations", "orgs", "data", "result", "items", "api_keys", "keys")) {
        if ($Value.PSObject.Properties.Name -contains $propertyName) {
            return Get-Items $Value.$propertyName
        }
    }
    return @($Value)
}

function Get-OrgId {
    param($Org)

    foreach ($propertyName in @("id", "slug", "organization_id")) {
        if ($Org.PSObject.Properties.Name -contains $propertyName) {
            $value = [string]$Org.$propertyName
            if ($value) {
                return $value
            }
        }
    }
    return ""
}

function Get-OrgLabel {
    param($Org)

    foreach ($propertyName in @("name", "slug", "id")) {
        if ($Org.PSObject.Properties.Name -contains $propertyName) {
            $value = [string]$Org.$propertyName
            if ($value) {
                return $value
            }
        }
    }
    return "(unnamed organization)"
}

function Resolve-DefaultOrgId {
    param($Organizations, [string]$PreferredOrgId)

    $items = @(Get-Items $Organizations)
    if ($PreferredOrgId) {
        foreach ($org in $items) {
            foreach ($propertyName in @("id", "slug", "organization_id")) {
                if (
                    ($org.PSObject.Properties.Name -contains $propertyName) -and
                    ([string]$org.$propertyName -eq $PreferredOrgId)
                ) {
                    return $PreferredOrgId
                }
            }
        }
    }
    if ($items.Count -eq 1) {
        return Get-OrgId $items[0]
    }
    return ""
}

function Resolve-OrgInput {
    param($Organizations, [string]$InputValue)

    $trimmed = ""
    if ($InputValue) {
        $trimmed = $InputValue.Trim()
    }
    if (-not $trimmed) {
        return ""
    }
    foreach ($org in @(Get-Items $Organizations)) {
        $orgId = Get-OrgId $org
        $labels = @($orgId, (Get-OrgLabel $org))
        foreach ($propertyName in @("name", "slug", "id", "organization_id")) {
            if ($org.PSObject.Properties.Name -contains $propertyName) {
                $labels += [string]$org.$propertyName
            }
        }
        foreach ($label in $labels) {
            if ($label -and $label.Trim().Equals($trimmed, [StringComparison]::OrdinalIgnoreCase)) {
                return $orgId
            }
        }
    }
    return $trimmed
}

function Get-ProjectByName {
    param($Projects, [string]$ProjectName)

    foreach ($project in Get-Items $Projects) {
        $name = [string]($project.name)
        if ($name -eq $ProjectName) {
            return $project
        }
    }
    return $null
}

function Get-ProjectRef {
    param($Project)

    foreach ($propertyName in @("ref", "project_ref", "id")) {
        if ($Project.PSObject.Properties.Name -contains $propertyName) {
            $value = [string]$Project.$propertyName
            if ($value) {
                return $value
            }
        }
    }
    throw "Unable to determine Supabase project ref from project list."
}

function Get-KeyValue {
    param($KeyObject)

    foreach ($propertyName in @("api_key", "key", "value", "token")) {
        if ($KeyObject.PSObject.Properties.Name -contains $propertyName) {
            $value = [string]$KeyObject.$propertyName
            if ($value) {
                return $value
            }
        }
    }
    return ""
}

function Find-PublicKey {
    param($ApiKeys)

    foreach ($item in Get-Items $ApiKeys) {
        $value = Get-KeyValue $item
        if ($value.StartsWith("sb_publishable_")) {
            return @{ Value = $value; Type = "publishable" }
        }
    }
    foreach ($item in Get-Items $ApiKeys) {
        $name = ([string]($item.name)).ToLowerInvariant()
        $value = Get-KeyValue $item
        if (($name -eq "anon" -or $name -eq "anon_key") -and $value) {
            return @{ Value = $value; Type = "anon" }
        }
    }
    throw "Unable to find a Supabase publishable or anon key."
}

function Find-AdminKey {
    param($ApiKeys)

    foreach ($item in Get-Items $ApiKeys) {
        $value = Get-KeyValue $item
        if ($value.StartsWith("sb_secret_")) {
            return @{ Value = $value; Type = "secret" }
        }
    }
    foreach ($item in Get-Items $ApiKeys) {
        $name = ([string]($item.name)).ToLowerInvariant()
        $value = Get-KeyValue $item
        if (($name -eq "service_role" -or $name -eq "service_role_key") -and $value) {
            return @{ Value = $value; Type = "service_role" }
        }
    }
    return $null
}

function Update-ClientSettings {
    param([string]$Path, [string]$ProjectUrl, [string]$PublicKey)

    if (-not (Test-Path $Path)) {
        return
    }
    $text = Get-Content -Raw -LiteralPath $Path
    $text = $text -replace '(?m)^SUPABASE_PROJECT_URL = ".*"$', ('SUPABASE_PROJECT_URL = "' + $ProjectUrl + '"')
    $text = $text -replace '(?m)^SUPABASE_ANON_KEY = ".*"$', ('SUPABASE_ANON_KEY = "' + $PublicKey + '"')
    Set-Content -LiteralPath $Path -Value $text -Encoding UTF8
}

function New-OperatorUser {
    param(
        [string]$ProjectUrl,
        [string]$AdminKey,
        [string]$Email,
        [string]$Password
    )

    $headers = @{
        "apikey" = $AdminKey
        "Authorization" = "Bearer $AdminKey"
        "Content-Type" = "application/json"
    }
    $body = @{
        email = $Email
        password = $Password
        email_confirm = $true
    } | ConvertTo-Json -Compress

    try {
        Invoke-RestMethod `
            -Method Post `
            -Uri "$ProjectUrl/auth/v1/admin/users" `
            -Headers $headers `
            -Body $body `
            -UserAgent "LOL-Tournament-Code-Creator-Deploy/1.0" | Out-Null
        Write-Host "Operator Auth user created: $Email"
    } catch {
        $message = $_.Exception.Message
        if ($message -match "already|registered|422|duplicate|exists") {
            Write-Host "Operator Auth user already exists: $Email" -ForegroundColor Yellow
            return
        }
        Write-Host "Operator Auth user could not be created automatically." -ForegroundColor Yellow
        Write-Host "Create it manually in Supabase Dashboard > Authentication > Users." -ForegroundColor Yellow
        Write-DeployLog "Operator Auth user auto-create skipped after error: $message"
        return
    }
}

Set-Location $RootDir
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $SummaryPath) | Out-Null

Write-Host "LOL Tournament Code Creator - Supabase approval-ready deploy" -ForegroundColor Green
Write-Host "Create a Supabase account access token, not a project API key."
Write-Host "This token can be created before the Supabase project exists."
Write-Host "Create it at:"
Write-Host "https://supabase.com/dashboard/account/tokens"
Write-Host "Paste secrets only into this PowerShell window. Do not paste them into chat."

if ($SkipPredeploy) {
    Write-Host ""
    Write-Host "== Local predeploy checks ==" -ForegroundColor Cyan
    Write-Host "Skipped for this deployment run. Run npm run predeploy separately before release." -ForegroundColor Yellow
    Write-DeployLog "SKIP: Local predeploy checks"
} else {
    Invoke-CheckedCommand "Local predeploy checks" @("npm.cmd", "run", "predeploy")
}

$supabaseToken = Read-SecretValue "Supabase account access token"
$env:SUPABASE_ACCESS_TOKEN = $supabaseToken
$script:SupabaseAccountToken = $supabaseToken
Write-DeployLog "Supabase account access token received from local prompt."

$organizations = Invoke-SupabaseManagementApi "List Supabase organizations" "GET" "/organizations"
$orgDefault = Resolve-DefaultOrgId $organizations $DefaultOrgId
$orgItems = @(Get-Items $organizations)
if ($orgItems.Count -gt 0) {
    Write-Host ""
    Write-Host "Available Supabase organizations:" -ForegroundColor Cyan
    foreach ($org in $orgItems) {
        Write-Host ("- {0} : {1}" -f (Get-OrgId $org), (Get-OrgLabel $org))
    }
}
if (-not $orgDefault) {
    Write-Host "Choose the organization ID from the list above." -ForegroundColor Yellow
}

$orgInput = Read-RequiredValue "Supabase organization ID or name" $orgDefault
$orgId = Resolve-OrgInput $organizations $orgInput
if ($orgId -ne $orgInput) {
    Write-Host "Resolved organization '$orgInput' to ID '$orgId'." -ForegroundColor Cyan
    Write-DeployLog "Resolved organization input to id=$orgId"
}
$projectName = Read-RequiredValue "Supabase project name" $DefaultProjectName
$region = Read-RequiredValue "Supabase region" $DefaultRegion
Write-DeployLog "Target project: org=$orgId project=$projectName region=$region"

$projects = Invoke-SupabaseManagementApi "List Supabase projects" "GET" "/projects"
$project = Get-ProjectByName $projects $projectName

if ($null -eq $project) {
    Write-Host ""
    Write-Host "The next step creates a Supabase project through the Management API." -ForegroundColor Yellow
    Write-Host "Use a strong password and keep it in your password manager."
    $dbPassword = Read-SecretValue "Supabase database password for the new project"
    $project = Invoke-SupabaseManagementApi "Create Supabase project" "POST" "/projects" @{
        organization_id = $orgId
        name = $projectName
        region = $region
        db_pass = $dbPassword
    }

    Write-Host "Waiting for the project to appear in Supabase..." -ForegroundColor Yellow
    Write-DeployLog "Waiting for project to appear."
    for ($attempt = 1; $attempt -le 40; $attempt++) {
        Start-Sleep -Seconds 10
        $projects = Invoke-SupabaseManagementApi "Refresh Supabase projects" "GET" "/projects"
        $project = Get-ProjectByName $projects $projectName
        if ($null -ne $project) {
            break
        }
    }
}

if ($null -eq $project) {
    throw "Supabase project was not found after creation."
}

$projectRef = Get-ProjectRef $project
$projectUrl = "https://$projectRef.supabase.co"
$callbackUrl = "$projectUrl/functions/v1/riot-callback"
$callbackSecret = New-CallbackSecret
Write-Host "Using project: $projectName ($projectRef)"
Write-DeployLog "Using project ref: $projectRef"

$apiKeys = $null
for ($attempt = 1; $attempt -le 40; $attempt++) {
    try {
        $apiKeys = Invoke-SupabaseManagementApi "Read Supabase API keys" "GET" "/projects/$projectRef/api-keys"
        break
    } catch {
        if ($attempt -eq 40) {
            throw
        }
        Write-Host "Project is not ready yet. Waiting..." -ForegroundColor Yellow
        Start-Sleep -Seconds 10
    }
}

$publicKey = Find-PublicKey $apiKeys
$adminKey = Find-AdminKey $apiKeys

Update-ClientSettings (Join-Path $RootDir "client_settings.py") $projectUrl $publicKey.Value
Update-ClientSettings (Join-Path $RootDir "LOL_Tournament_Code_Creator-main\src\client_settings.py") $projectUrl $publicKey.Value
Write-Host "Client settings updated with Supabase project URL and public key."
Write-DeployLog "Client settings updated."

$operatorEmail = Read-RequiredValue "Operator email allowed to use the app"
$operatorPassword = Read-SecretValue "Operator password to create/use"
$riotApiKey = Read-SecretValue "Riot API key (development before Riot approval; production after approval)"
if (-not $riotApiKey.StartsWith("RGAPI-")) {
    throw "Riot API key must start with RGAPI-."
}

if ($null -ne $adminKey) {
    New-OperatorUser $projectUrl $adminKey.Value $operatorEmail $operatorPassword
} else {
    Write-Host "No Supabase admin key was returned by the CLI. Create the operator user manually in Authentication > Users." -ForegroundColor Yellow
    Write-DeployLog "Admin key unavailable; operator user must be created manually."
}

$tempSecrets = Join-Path ([IO.Path]::GetTempPath()) ("lol-tournament-supabase-secrets-" + [Guid]::NewGuid().ToString("N") + ".env")
$env:SUPABASE_SECRETS_FILE = $tempSecrets

try {
    @(
        "RIOT_API_KEY=$riotApiKey",
        "RIOT_CALLBACK_URL=$callbackUrl",
        "RIOT_CALLBACK_SECRET=$callbackSecret",
        "ALLOWED_OPERATOR_EMAILS=$operatorEmail"
    ) | Set-Content -LiteralPath $tempSecrets -Encoding UTF8

    Invoke-CheckedCommand "Validate Supabase secrets" @("npm.cmd", "run", "secrets:check")
    Invoke-CheckedCommand "Upload Supabase secrets" @("npm.cmd", "run", "secrets:set")
    Invoke-CheckedCommand "Deploy Supabase Edge Functions" @("npm.cmd", "run", "functions:deploy")
    Invoke-CheckedCommand "Postdeploy verification" @("npm.cmd", "run", "postdeploy")
} finally {
    Remove-Item -LiteralPath $tempSecrets -Force -ErrorAction SilentlyContinue
    Remove-Item Env:\SUPABASE_SECRETS_FILE -ErrorAction SilentlyContinue
    Remove-Item Env:\SUPABASE_ACCESS_TOKEN -ErrorAction SilentlyContinue
}

$summary = [ordered]@{
    project_name = $projectName
    project_ref = $projectRef
    project_url = $projectUrl
    public_key_type = $publicKey.Type
    callback_url = $callbackUrl
    functions = @("riot-tournament", "riot-callback")
    completed_at = (Get-Date).ToUniversalTime().ToString("o")
}
$summary | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $SummaryPath -Encoding UTF8
Write-DeployLog "Deployment completed. Summary written."

Write-Host ""
Write-Host "Supabase approval-ready deploy completed." -ForegroundColor Green
Write-Host "Summary: $SummaryPath"
Read-Host "Press Enter to close"
