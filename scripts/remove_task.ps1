$TaskName = "AniData-CD"

$existing = schtasks /query /tn $TaskName 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "Aucune tache $TaskName trouvee."
    exit 0
}

schtasks /delete /tn $TaskName /f | Out-Null
Write-Host "Tache $TaskName supprimee."
