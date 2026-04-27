$RunnerDir = Join-Path $HOME "anidata-runner"

if (-not (Test-Path $RunnerDir)) {
    Write-Host "Aucun runner AniData trouve dans $RunnerDir"
    exit 0
}

Set-Location $RunnerDir

$token = Read-Host "Token de suppression GitHub (laisse vide si tu le supprimes manuellement sur GitHub)"

if (-not [string]::IsNullOrEmpty($token)) {
    & ".\config.cmd" remove --token $token
} else {
    Write-Host "Supprime le runner manuellement sur GitHub :"
    Write-Host "  github.com/{repo}/settings/actions/runners"
}

Set-Location $HOME
Remove-Item $RunnerDir -Recurse -Force

[System.Environment]::SetEnvironmentVariable("ANIDATA_PROJECT_DIR", $null, "User")

Write-Host "Runner supprime."
