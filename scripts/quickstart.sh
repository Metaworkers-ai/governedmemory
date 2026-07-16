#!/usr/bin/env bash

# Start the local GovernedMemory demo. This wrapper handles the common case
# where Docker Desktop is installed on macOS but the daemon is not running.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if ! command -v docker >/dev/null 2>&1; then
  cat >&2 <<'EOF'
Docker is required for the local Quickstart but was not found.
Install Docker Desktop: https://docs.docker.com/desktop/
Then rerun: ./scripts/quickstart.sh
Prefer zero-install? Use the hosted sandbox from the project README.
EOF
  exit 127
fi

docker_running() {
  docker info >/dev/null 2>&1
}

if ! docker_running; then
  case "$(uname -s)" in
    Darwin)
      if [ -d "/Applications/Docker.app" ] || [ -d "$HOME/Applications/Docker.app" ]; then
        echo "Docker Desktop is installed but stopped; starting it..."
        open -g -a Docker >/dev/null 2>&1 || true
      else
        cat >&2 <<'EOF'
Docker is installed as a command-line client, but Docker Desktop was not found.
Install Docker Desktop: https://docs.docker.com/desktop/install/mac-install/
EOF
        exit 1
      fi
      ;;
    Linux)
      if command -v systemctl >/dev/null 2>&1 && systemctl list-unit-files docker.service >/dev/null 2>&1; then
        echo "Docker is installed but stopped; attempting to start the Docker service..."
        systemctl start docker >/dev/null 2>&1 || true
      fi
      ;;
  esac
fi

if ! docker_running; then
  echo "Waiting for the Docker daemon (up to 120 seconds)..."
  for _ in $(seq 1 60); do
    if docker_running; then
      break
    fi
    sleep 2
  done
fi

if ! docker_running; then
  cat >&2 <<'EOF'
Docker is installed but the daemon is still unavailable.
Start Docker Desktop manually, wait for it to finish loading, and rerun:
  ./scripts/quickstart.sh
EOF
  exit 1
fi

port_in_use() {
  if command -v lsof >/dev/null 2>&1 && lsof -nP -iTCP:"$1" -sTCP:LISTEN >/dev/null 2>&1; then
    return 0
  fi
  if command -v nc >/dev/null 2>&1 && nc -z 127.0.0.1 "$1" >/dev/null 2>&1; then
    return 0
  fi
  return 1
}

if [ -z "${POSTGRES_HOST_PORT:-}" ]; then
  # Reuse the port of an already-running Quickstart stack so repeated runs do
  # not recreate Postgres just because another process owns 5432.
  existing_postgres="$(docker compose -f deploy/docker-compose.yml ps -q postgres 2>/dev/null || true)"
  existing_port=""
  if [ -n "$existing_postgres" ]; then
    existing_port="$(docker port "$existing_postgres" 5432/tcp 2>/dev/null | sed -n 's/.*://p' | head -n 1)"
  fi

  POSTGRES_HOST_PORT="${existing_port:-5432}"
  if [ -z "$existing_port" ] && port_in_use "$POSTGRES_HOST_PORT"; then
    found_port=0
    for candidate in $(seq 5433 5442); do
      if ! port_in_use "$candidate"; then
        POSTGRES_HOST_PORT="$candidate"
        echo "Host port 5432 is busy; using Postgres host port $POSTGRES_HOST_PORT instead."
        found_port=1
        break
      fi
    done
    if [ "$found_port" -eq 0 ]; then
      echo "Host ports 5432-5442 are all busy; stop one or set POSTGRES_HOST_PORT manually." >&2
      exit 1
    fi
  fi
fi
export POSTGRES_HOST_PORT

echo "Docker is ready. Starting GovernedMemory..."
exec docker compose -f deploy/docker-compose.yml --profile seed up --build -d
