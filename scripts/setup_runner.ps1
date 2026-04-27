$ScriptDir  = $PSScriptRoot
$ProjectDir = Split-Path -Parent $ScriptDir
$EnvFile    = Join-Path $ProjectDir ".env"
$RunnerDir  = Join-Path $HOME "anidata-runner"

$envVars = @{}
Get-Content $EnvFile | Where-Object { $_ -notmatch '^\s*#' -and $_ -match '=' } | ForEach-Object {
    $parts = $_ -split '=', 2
    if ($parts.Count -eq 2) { $envVars[$parts[0].Trim()] = $parts[1].Trim() }
}

$GithubRepository = $envVars['GITHUB_REPOSITORY']
$RepoUrl          = "https://github.com/$GithubRepository"
$TokenPageUrl     = "$RepoUrl/settings/actions/runners/new?runnerOs=win"

$pathFile = Join-Path $RunnerDir "project_path.txt"
New-Item -ItemType Directory -Force -Path $RunnerDir | Out-Null
Set-Content -Path $pathFile -Value $ProjectDir -Encoding UTF8
Write-Host "Chemin projet sauvegarde : $pathFile"

Write-Host ""
Write-Host "Ouvre ce lien dans ton navigateur :"
Write-Host "  $TokenPageUrl"
Write-Host ""
Write-Host "Selectionne : Windows x64"
Write-Host "Repere la ligne : --token XXXXXXXXXX"
Write-Host "Copie uniquement la valeur du token (apres --token)"
Write-Host ""

$token = Read-Host "Colle le token GitHub ici"

if ([string]::IsNullOrEmpty($token)) {
    Write-Host "ERREUR: token vide"
    exit 1
}

New-Item -ItemType Directory -Force -Path $RunnerDir | Out-Null

Write-Host "Telechargement du runner GitHub Actions..."
$release = Invoke-RestMethod "https://api.github.com/repos/actions/runner/releases/latest"
$asset   = $release.assets | Where-Object { $_.name -like "actions-runner-win-x64-*.zip" } | Select-Object -First 1

if (-not $asset) {
    Write-Host "ERREUR: impossible de trouver l'archive du runner"
    exit 1
}

$zipPath = Join-Path $env:TEMP "actions-runner.zip"
Invoke-WebRequest -Uri $asset.browser_download_url -OutFile $zipPath
Expand-Archive -Path $zipPath -DestinationPath $RunnerDir -Force
Remove-Item $zipPath

Write-Host "Configuration du runner..."
Set-Location $RunnerDir
& ".\config.cmd" --url $RepoUrl --token $token --name "anidata-local" --labels "self-hosted" --unattended

Write-Host ""
Write-Host "Runner configure."
Write-Host ""
Write-Host "Pour le demarrer (laisse ce terminal ouvert) :"
Write-Host "  cd $RunnerDir"
Write-Host "  .\run.cmd"
Write-Host ""
Write-Host "Verifie qu'il apparait ici :"
Write-Host "  $RepoUrl/settings/actions/runners"
