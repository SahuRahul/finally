# Build (if needed) and run the FinAlly container. Idempotent.
param([switch]$Build)

$ErrorActionPreference = "Stop"

$Image = "finally"
$Container = "finally"
$Volume = "finally-data"
$Port = 8000

Set-Location (Join-Path $PSScriptRoot "..")

$exists = docker image inspect $Image 2>$null
if ($Build -or -not $exists) {
    Write-Host "Building image $Image..."
    docker build -t $Image .
}

# Remove any existing container so this is safe to re-run.
docker rm -f $Container 2>$null | Out-Null

Write-Host "Starting container $Container..."
docker run -d `
    --name $Container `
    -p "${Port}:8000" `
    --env-file .env `
    -v "${Volume}:/data" `
    $Image

Write-Host "FinAlly is running at http://localhost:$Port"
