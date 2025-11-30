# StatusMonitor Docker Shutdown Script
# This script stops all StatusMonitor services

param(
    [switch]$Clean
)

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  StatusMonitor - Docker Shutdown" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "Stopping services..." -ForegroundColor Yellow
docker-compose down

if ($Clean) {
    Write-Host ""
    Write-Host "Cleaning up volumes and images..." -ForegroundColor Yellow
    docker-compose down -v --rmi all
    Write-Host "✓ Cleanup completed" -ForegroundColor Green
}
else {
    Write-Host "✓ Services stopped" -ForegroundColor Green
    Write-Host ""
    Write-Host "To also remove volumes and images, run: .\stop-docker.ps1 -Clean" -ForegroundColor Yellow
}

Write-Host ""
