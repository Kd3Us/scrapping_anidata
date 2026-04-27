$TaskName    = "AniData-CD"
$ScriptDir   = $PSScriptRoot
$DeployScript = Join-Path $ScriptDir "check_and_deploy.ps1"
$LogFile     = Join-Path $env:TEMP "anidata_deploy.log"

if (-not (Test-Path $DeployScript)) {
    Write-Host "ERREUR: $DeployScript introuvable"
    exit 1
}

$existing = schtasks /query /tn $TaskName 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "La tache $TaskName est deja installee."
    exit 0
}

$taskArgs = "-NonInteractive -ExecutionPolicy Bypass -File `"$DeployScript`""
schtasks /create /tn $TaskName /tr "powershell.exe $taskArgs" /sc MINUTE /mo 5 /f | Out-Null

if ($LASTEXITCODE -ne 0) {
    Write-Host "ERREUR: impossible de creer la tache planifiee"
    exit 1
}

Write-Host "Tache installee : $TaskName (toutes les 5 minutes)"
Write-Host "Logs dans       : $LogFile"
