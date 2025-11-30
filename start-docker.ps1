# StatusMonitor Docker Startup Script
# This script builds and starts all StatusMonitor services using Docker Compose

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  StatusMonitor - Docker Startup" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check if Docker is running
try {
    docker info | Out-Null
    Write-Host "✓ Docker is running" -ForegroundColor Green
}
catch {
    Write-Host "✗ Docker is not running. Please start Docker Desktop." -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "Building Docker images..." -ForegroundColor Yellow
docker-compose build

if ($LASTEXITCODE -ne 0) {
    Write-Host "✗ Build failed. Please check the error messages above." -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "✓ Build completed successfully" -ForegroundColor Green
Write-Host ""
Write-Host "Starting services..." -ForegroundColor Yellow
docker-compose up -d

if ($LASTEXITCODE -ne 0) {
    Write-Host "✗ Failed to start services. Please check the error messages above." -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "✓ All services started successfully!" -ForegroundColor Green
Write-Host ""
Write-Host "Services running at:" -ForegroundColor Cyan
Write-Host "  Frontend:       http://localhost:5173" -ForegroundColor White
Write-Host "  Auth Service:   http://localhost:8000" -ForegroundColor White
Write-Host "  Ingestion:      http://localhost:8001" -ForegroundColor White
Write-Host "  Distribution:   http://localhost:8002" -ForegroundColor White
Write-Host "  Redis:          localhost:6379" -ForegroundColor White
Write-Host ""
Write-Host "To view logs: docker-compose logs -f" -ForegroundColor Yellow
Write-Host "To stop:      docker-compose down" -ForegroundColor Yellow
Write-Host ""
