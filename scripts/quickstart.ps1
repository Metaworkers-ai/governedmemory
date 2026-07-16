# Start the local GovernedMemory demo from Windows PowerShell.

$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

if (-not $env:COMPOSE_PROJECT_NAME) {
    $projectName = (Split-Path -Leaf (Get-Location)).ToLower() -replace "[^a-z0-9_-]", "-"
    if (-not $projectName) { $projectName = "governedmemory" }
    $env:COMPOSE_PROJECT_NAME = $projectName
}

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Error @"
Docker is required for the local Quickstart but was not found.
Install Docker Desktop: https://docs.docker.com/desktop/
Then rerun: .\scripts\quickstart.ps1
Prefer zero-install? Use the hosted sandbox from the project README.
"@
}

function Test-DockerRunning {
    docker info *> $null
    return $LASTEXITCODE -eq 0
}

if (-not (Test-DockerRunning)) {
    $desktopCandidates = @(
        (Join-Path ${env:ProgramFiles} "Docker\Docker\Docker Desktop.exe"),
        (Join-Path ${env:LocalAppData} "Docker\Docker Desktop.exe")
    )
    $desktop = $desktopCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
    if ($desktop) {
        Write-Host "Docker Desktop is installed but stopped; starting it..."
        Start-Process -FilePath $desktop
    }
}

if (-not (Test-DockerRunning)) {
    Write-Host "Waiting for the Docker daemon (up to 120 seconds)..."
    for ($i = 0; $i -lt 60; $i++) {
        if (Test-DockerRunning) { break }
        Start-Sleep -Seconds 2
    }
}

if (-not (Test-DockerRunning)) {
    Write-Error @"
Docker is installed but the daemon is still unavailable.
Start Docker Desktop manually, wait for it to finish loading, and rerun:
  .\scripts\quickstart.ps1
"@
}

$postgresPort = $env:POSTGRES_HOST_PORT
if (-not $postgresPort) {
    $existingPostgres = docker compose -f deploy/docker-compose.yml ps -q postgres 2>$null
    $existingPort = ""
    if ($existingPostgres) {
        $existingPort = (docker port $existingPostgres 5432/tcp 2>$null | Select-Object -First 1) -replace ".*:", ""
    }

    $postgresPort = if ($existingPort) { $existingPort } else { 5432 }
    $portBusy = Get-NetTCPConnection -LocalPort $postgresPort -State Listen -ErrorAction SilentlyContinue
    if (-not $existingPort -and $portBusy) {
        $foundPort = $false
        5433..5442 | ForEach-Object {
            if (-not $foundPort) {
                $candidateBusy = Get-NetTCPConnection -LocalPort $_ -State Listen -ErrorAction SilentlyContinue
                if (-not $candidateBusy) { $postgresPort = $_; $foundPort = $true }
            }
        }
        if (-not $foundPort) {
            Write-Error "Host ports 5432-5442 are all busy; stop one or set POSTGRES_HOST_PORT manually."
        }
        Write-Host "Host port 5432 is busy; using Postgres host port $postgresPort instead."
    }
}
$env:POSTGRES_HOST_PORT = $postgresPort

Write-Host "Docker is ready. Starting GovernedMemory..."
docker compose -f deploy/docker-compose.yml --profile seed up --build -d

Write-Host "Waiting for the demo seed and application health..."
$seedContainer = ""
for ($i = 0; $i -lt 60; $i++) {
    $seedContainer = (docker compose -f deploy/docker-compose.yml ps -aq seed 2>$null | Select-Object -First 1)
    if ($seedContainer) {
        $seedState = docker inspect -f '{{.State.Status}} {{.State.ExitCode}}' $seedContainer 2>$null
        if ($seedState -eq "exited 0") { break }
        if ($seedState -like "exited *") {
            Write-Host "The demo seed failed ($seedState). Recent seed logs:"
            docker compose -f deploy/docker-compose.yml logs --tail=50 seed
            exit 1
        }
    }
    Start-Sleep -Seconds 1
}

if (-not $seedContainer -or (docker inspect -f '{{.State.Status}} {{.State.ExitCode}}' $seedContainer 2>$null) -ne "exited 0") {
    Write-Host "The demo seed did not finish within 60 seconds. Recent seed logs:"
    docker compose -f deploy/docker-compose.yml logs --tail=50 seed
    exit 1
}

$apiReady = $false
$webReady = $false
for ($i = 0; $i -lt 60; $i++) {
    if (-not $apiReady) {
        try { Invoke-WebRequest -UseBasicParsing -Uri "http://localhost:8000/healthz" -TimeoutSec 2 | Out-Null; $apiReady = $true } catch {}
    }
    if (-not $webReady) {
        try { Invoke-WebRequest -UseBasicParsing -Uri "http://localhost:3000" -TimeoutSec 2 | Out-Null; $webReady = $true } catch {}
    }
    if ($apiReady -and $webReady) { break }
    Start-Sleep -Seconds 1
}

if (-not ($apiReady -and $webReady)) {
    Write-Host "The GovernedMemory services did not become ready within 60 seconds."
    docker compose -f deploy/docker-compose.yml ps
    exit 1
}

Write-Host @"

GovernedMemory is ready.

Web console: http://localhost:3000
API health:  http://localhost:8000/healthz

Next steps:
1. Open the web console.
2. Go to Write.
3. Submit the example injection text from the README.
4. Open Audit Log to inspect the blocked event.
"@
