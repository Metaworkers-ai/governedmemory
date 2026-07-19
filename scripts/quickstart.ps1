# Start, stop, or reset the local GovernedMemory demo from Windows PowerShell.

param(
    [ValidateSet("up", "down", "reset")]
    [string]$Action = "up"
)

$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

$composeFile = "deploy/docker-compose.yml"
function Invoke-Compose {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Arguments)
    $previousPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = "SilentlyContinue"
        docker compose -f $composeFile @Arguments 2>$null
        $script:LastComposeExitCode = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $previousPreference
    }
}

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
    $previousPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = "SilentlyContinue"
        docker info 2>&1 | Out-Null
        return $LASTEXITCODE -eq 0
    } finally {
        $ErrorActionPreference = $previousPreference
    }
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

if ($Action -eq "down") {
    Write-Host "Stopping Compose project '$env:COMPOSE_PROJECT_NAME' (volumes preserved)..."
    Invoke-Compose -Arguments @("down")
    exit $script:LastComposeExitCode
}

if ($Action -eq "reset") {
    Write-Host "WARNING: resetting Compose project '$env:COMPOSE_PROJECT_NAME' will delete its demo data and volumes."
    Write-Host "Removing containers, networks, and volumes..."
    Invoke-Compose -Arguments @("down", "-v")
    exit $script:LastComposeExitCode
}

function Test-HostPortBusy {
    param([int]$Port)
    return [bool](Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)
}

function Get-ExistingMappedPort {
    param([string]$Service, [int]$ContainerPort)
    $container = Invoke-Compose -Arguments @("ps", "-aq", $Service) | Select-Object -First 1
    if ($script:LastComposeExitCode -ne 0) { return $null }
    if (-not $container) { return $null }
    $previousPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = "SilentlyContinue"
        $raw = docker inspect -f '{{json .HostConfig.PortBindings}}' $container 2>$null
        $inspectExitCode = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $previousPreference
    }
    if ($inspectExitCode -ne 0) { return $null }
    if (-not $raw) { return $null }
    try {
        $bindings = $raw | ConvertFrom-Json
        $property = $bindings.PSObject.Properties | Where-Object { $_.Name -eq "$ContainerPort/tcp" } | Select-Object -First 1
        if ($property -and $property.Value) { return [int]$property.Value[0].HostPort }
    } catch {}
    return $null
}

function Resolve-HostPort {
    param([string]$EnvironmentName, [string]$Service, [int]$ContainerPort, [int]$DefaultPort, [int]$MaxPort)
    $requested = [Environment]::GetEnvironmentVariable($EnvironmentName)
    if ($requested) { return [int]$requested }
    $existing = Get-ExistingMappedPort $Service $ContainerPort
    if ($existing) { return $existing }
    for ($candidate = $DefaultPort; $candidate -le $MaxPort; $candidate++) {
        if (-not (Test-HostPortBusy $candidate)) { return $candidate }
    }
    throw "Host ports $DefaultPort-$MaxPort are all busy; stop one or set $EnvironmentName manually."
}

function Get-ContainerState {
    param([string]$Container)
    $previousPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = "SilentlyContinue"
        $state = docker inspect -f '{{.State.Status}} {{.State.ExitCode}}' $Container 2>$null
        $script:LastInspectExitCode = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $previousPreference
    }
    if ($script:LastInspectExitCode -ne 0) { return $null }
    return $state
}

$postgresPortSupplied = $env:POSTGRES_HOST_PORT
$apiPortSupplied = $env:API_HOST_PORT
$webPortSupplied = $env:WEB_HOST_PORT
$postgresExistingPort = Get-ExistingMappedPort postgres 5432
$apiExistingPort = Get-ExistingMappedPort api 8000
$webExistingPort = Get-ExistingMappedPort web 3000
$postgresPort = Resolve-HostPort POSTGRES_HOST_PORT postgres 5432 5432 5442
$apiPort = Resolve-HostPort API_HOST_PORT api 8000 8000 8010
$webPort = Resolve-HostPort WEB_HOST_PORT web 3000 3000 3010
$env:POSTGRES_HOST_PORT = $postgresPort
$env:API_HOST_PORT = $apiPort
$env:WEB_HOST_PORT = $webPort
if (-not $postgresPortSupplied -and -not $postgresExistingPort -and $postgresPort -ne 5432) { Write-Host "Host port 5432 is busy; using Postgres host port $postgresPort instead." }
if (-not $apiPortSupplied -and -not $apiExistingPort -and $apiPort -ne 8000) { Write-Host "Host port 8000 is busy; using API host port $apiPort instead." }
if (-not $webPortSupplied -and -not $webExistingPort -and $webPort -ne 3000) { Write-Host "Host port 3000 is busy; using web host port $webPort instead." }

function Write-Diagnostics {
    param([string]$FailedService)
    Write-Host "Quickstart failed for Compose project '$env:COMPOSE_PROJECT_NAME'."
    Write-Host "Host ports: Postgres $env:POSTGRES_HOST_PORT, API $env:API_HOST_PORT, Web $env:WEB_HOST_PORT"
    Invoke-Compose -Arguments @("ps")
    if ($FailedService -eq "startup") {
        $services = @("postgres", "schema", "api", "seed", "web")
    } else {
        $services = @($FailedService)
    }
    foreach ($service in $services) {
        Write-Host "--- recent $service logs ---"
        Invoke-Compose -Arguments @("logs", "--tail=50", $service)
    }
}

Write-Host "Docker is ready. Starting GovernedMemory..."
Invoke-Compose -Arguments @("--profile", "seed", "up", "--build", "-d")
if ($script:LastComposeExitCode -ne 0) {
    Write-Diagnostics "startup"
    exit $script:LastComposeExitCode
}

Write-Host "Waiting for the demo seed and application health..."
$seedContainer = ""
for ($i = 0; $i -lt 60; $i++) {
    $seedContainer = (Invoke-Compose -Arguments @("ps", "-aq", "seed") | Select-Object -First 1)
    if ($seedContainer) {
        $seedState = Get-ContainerState $seedContainer
        if ($seedState -eq "exited 0") { break }
        if ($seedState -like "exited *") {
            Write-Host "The demo seed failed ($seedState)."
            Write-Diagnostics "seed"
            exit 1
        }
    }
    Start-Sleep -Seconds 1
}

if (-not $seedContainer -or (Get-ContainerState $seedContainer) -ne "exited 0") {
    Write-Host "The demo seed did not finish within 60 seconds."
    Write-Diagnostics "seed"
    exit 1
}

$apiReady = $false
$webReady = $false
for ($i = 0; $i -lt 60; $i++) {
    if (-not $apiReady) {
        try { Invoke-WebRequest -UseBasicParsing -Uri "http://localhost:$apiPort/healthz" -TimeoutSec 2 | Out-Null; $apiReady = $true } catch {}
    }
    if (-not $webReady) {
        try { Invoke-WebRequest -UseBasicParsing -Uri "http://localhost:$webPort" -TimeoutSec 2 | Out-Null; $webReady = $true } catch {}
    }
    if ($apiReady -and $webReady) { break }
    Start-Sleep -Seconds 1
}

if (-not ($apiReady -and $webReady)) {
    if (-not $apiReady) {
        Write-Host "The API did not become ready within 60 seconds."
        Write-Diagnostics "api"
    } else {
        Write-Host "The web console did not become ready within 60 seconds."
        Write-Diagnostics "web"
    }
    exit 1
}

$supportsAnsi = $Host.UI.SupportsVirtualTerminal
if ($supportsAnsi -and -not $env:NO_COLOR) {
    $esc = [char]27
    $boldGreen = "$esc[1;32m"
    $boldCyan = "$esc[1;36m"
    $bold = "$esc[1m"
    $reset = "$esc[0m"
    $osc8Start = "$esc]8;;"
    $osc8End = "$esc]8;;$esc\"
} else {
    $boldGreen = ""
    $boldCyan = ""
    $bold = ""
    $reset = ""
    $osc8Start = ""
    $osc8End = ""
}

function Write-Link {
    param([string]$Url, [string]$Label = $Url)
    if ($osc8Start) {
        Write-Host ($osc8Start + $Url + $esc + "\" + $boldCyan + $Label + $reset + $osc8End)
    } else {
        Write-Host "$boldCyan$Label$reset"
    }
}

Write-Host ""
Write-Host ($boldGreen + "GovernedMemory is ready." + $reset)
Write-Host ""
Write-Host -NoNewline ($bold + "Web console:" + $reset + " ")
Write-Link "http://localhost:$webPort"
Write-Host -NoNewline ($bold + "API health:" + $reset + "  ")
Write-Link "http://localhost:$apiPort/healthz"
Write-Host ""
Write-Host ($bold + "Next steps:" + $reset)
Write-Host "1. Open the web console."
Write-Host ("2. Go to " + $boldCyan + "Write" + $reset + ".")
Write-Host "3. Submit the example injection text from the README."
Write-Host ("4. Open " + $boldCyan + "Audit Log" + $reset + " to inspect the blocked event.")
