# Stop and remove the FinAlly container. Keeps the data volume. Idempotent.
$ErrorActionPreference = "Stop"

$Container = "finally"

$removed = docker rm -f $Container 2>$null
if ($removed) {
    Write-Host "Stopped and removed container $Container (data volume preserved)."
} else {
    Write-Host "Container $Container is not running."
}
