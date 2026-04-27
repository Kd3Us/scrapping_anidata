$ScriptDir  = $PSScriptRoot
$ProjectDir = Split-Path -Parent $ScriptDir
$LogFile    = Join-Path $env:TEMP "anidata_deploy.log"
$LastShaFile = Join-Path $ProjectDir ".last_deployed_sha"
$EnvFile    = Join-Path $ProjectDir ".env"

function Write-Log {
    param([string]$Message)
    $entry = "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] $Message"
    Add-Content -Path $LogFile -Value $entry -Encoding UTF8
    Write-Host $entry
}

if (-not (Test-Path $EnvFile)) {
    Write-Log "ERREUR: fichier .env introuvable dans $ProjectDir"
    exit 1
}

$envVars = @{}
Get-Content $EnvFile | Where-Object { $_ -notmatch '^\s*#' -and $_ -match '=' } | ForEach-Object {
    $parts = $_ -split '=', 2
    if ($parts.Count -eq 2) {
        $envVars[$parts[0].Trim()] = $parts[1].Trim()
    }
}

$GithubToken      = $envVars['GITHUB_TOKEN']
$GithubRepository = $envVars['GITHUB_REPOSITORY']

if ([string]::IsNullOrEmpty($GithubToken)) {
    Write-Log "ERREUR: GITHUB_TOKEN non defini dans .env"
    exit 1
}

if ([string]::IsNullOrEmpty($GithubRepository)) {
    Write-Log "ERREUR: GITHUB_REPOSITORY non defini dans .env"
    exit 1
}

$null = docker compose version 2>&1
if ($LASTEXITCODE -eq 0) {
    $UseNewCompose = $true
} elseif (Get-Command docker-compose -ErrorAction SilentlyContinue) {
    $UseNewCompose = $false
} else {
    Write-Log "ERREUR: docker compose introuvable"
    exit 1
}

$headers = @{
    "Authorization" = "Bearer $GithubToken"
    "Accept"        = "application/vnd.github+json"
}

try {
    $response = Invoke-RestMethod `
        -Uri "https://api.github.com/repos/$GithubRepository/actions/runs?branch=master&per_page=1" `
        -Headers $headers
} catch {
    Write-Log "ERREUR: impossible de joindre l'API GitHub - $($_.Exception.Message)"
    exit 1
}

$runs       = $response.workflow_runs
$conclusion = if ($runs -and $runs.Count -gt 0) { "$($runs[0].conclusion)" } else { "none" }
$headSha    = if ($runs -and $runs.Count -gt 0) { "$($runs[0].head_sha)" } else { "" }

if ($conclusion -ne "success") {
    Write-Log "CI pas verte ($conclusion), pas de deploiement"
    exit 0
}

$lastSha = ""
if (Test-Path $LastShaFile) {
    $lastSha = (Get-Content $LastShaFile -Raw).Trim()
}

if ($headSha -and $headSha -eq $lastSha) {
    Write-Log "Deja a jour, rien a faire"
    exit 0
}

Write-Log "Nouvelle image detectee (SHA: $headSha) - deploiement en cours..."

Set-Location $ProjectDir

if ($UseNewCompose) {
    docker compose pull 2>&1 | Add-Content $LogFile -Encoding UTF8
    docker compose up -d --no-deps airflow-webserver airflow-scheduler airflow-init 2>&1 | Add-Content $LogFile -Encoding UTF8
} else {
    docker-compose pull 2>&1 | Add-Content $LogFile -Encoding UTF8
    docker-compose up -d --no-deps airflow-webserver airflow-scheduler airflow-init 2>&1 | Add-Content $LogFile -Encoding UTF8
}

Set-Content -Path $LastShaFile -Value $headSha -Encoding UTF8
Write-Log "Deploiement OK - SHA: $headSha"
