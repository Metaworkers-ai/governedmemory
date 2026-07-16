#!/usr/bin/env bash

# Start, stop, or reset the local GovernedMemory demo. This wrapper handles
# Docker Desktop startup, clone-specific Compose projects, and host-port
# selection for concurrent local clones.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

usage() {
  cat <<'EOF'
Usage:
  ./scripts/quickstart.sh         Start or repeat the seeded Quickstart
  ./scripts/quickstart.sh down    Stop the stack and preserve its volumes
  ./scripts/quickstart.sh reset   Stop the stack and delete its volumes
EOF
}

ACTION="${1:-up}"
if [ "$#" -gt 1 ]; then
  usage >&2
  exit 2
fi
case "$ACTION" in
  up|down|reset) ;;
  -h|--help) usage; exit 0 ;;
  *) usage >&2; exit 2 ;;
esac

if [ -z "${COMPOSE_PROJECT_NAME:-}" ]; then
  COMPOSE_PROJECT_NAME="$(basename "$ROOT_DIR" | tr '[:upper:]' '[:lower:]' | sed -E 's/[^a-z0-9_-]/-/g; s/^[^a-z0-9]+//')"
  [ -n "$COMPOSE_PROJECT_NAME" ] || COMPOSE_PROJECT_NAME="governedmemory"
  export COMPOSE_PROJECT_NAME
fi

COMPOSE_FILE="deploy/docker-compose.yml"
compose() {
  docker compose -f "$COMPOSE_FILE" "$@"
}

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

if [ "$ACTION" = "down" ]; then
  echo "Stopping Compose project '$COMPOSE_PROJECT_NAME' (volumes preserved)..."
  compose down
  exit 0
fi

if [ "$ACTION" = "reset" ]; then
  echo "WARNING: resetting Compose project '$COMPOSE_PROJECT_NAME' will delete its demo data and volumes."
  echo "Removing containers, networks, and volumes..."
  compose down -v
  exit 0
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

existing_mapped_port() {
  local service="$1"
  local container_port="$2"
  local container
  container="$(compose ps -aq "$service" 2>/dev/null | head -n 1 || true)"
  [ -n "$container" ] || return 0
  docker inspect -f '{{range $p, $bindings := .HostConfig.PortBindings}}{{if eq $p "'"$container_port"'/tcp"}}{{(index $bindings 0).HostPort}}{{end}}{{end}}' "$container" 2>/dev/null | head -n 1
}

resolve_host_port() {
  local variable_name="$1"
  local service="$2"
  local container_port="$3"
  local default_port="$4"
  local max_port="$5"
  local requested="${!variable_name:-}"
  local existing
  local candidate

  if [ -n "$requested" ]; then
    printf '%s' "$requested"
    return 0
  fi

  existing="$(existing_mapped_port "$service" "$container_port")"
  if [ -n "$existing" ]; then
    printf '%s' "$existing"
    return 0
  fi

  for candidate in $(seq "$default_port" "$max_port"); do
    if ! port_in_use "$candidate"; then
      printf '%s' "$candidate"
      return 0
    fi
  done
  return 1
}

postgres_port_supplied="${POSTGRES_HOST_PORT:-}"
api_port_supplied="${API_HOST_PORT:-}"
web_port_supplied="${WEB_HOST_PORT:-}"
postgres_existing_port="$(existing_mapped_port postgres 5432)"
api_existing_port="$(existing_mapped_port api 8000)"
web_existing_port="$(existing_mapped_port web 3000)"

if ! POSTGRES_HOST_PORT="$(resolve_host_port POSTGRES_HOST_PORT postgres 5432 5432 5442)"; then
  echo "Host ports 5432-5442 are all busy; stop one or set POSTGRES_HOST_PORT manually." >&2
  exit 1
fi
if [ -z "$postgres_port_supplied" ] && [ -z "$postgres_existing_port" ] && [ "$POSTGRES_HOST_PORT" != "5432" ]; then
  echo "Host port 5432 is busy; using Postgres host port $POSTGRES_HOST_PORT instead." >&2
fi
export POSTGRES_HOST_PORT

if ! API_HOST_PORT="$(resolve_host_port API_HOST_PORT api 8000 8000 8010)"; then
  echo "Host ports 8000-8010 are all busy; stop one or set API_HOST_PORT manually." >&2
  exit 1
fi
if [ -z "$api_port_supplied" ] && [ -z "$api_existing_port" ] && [ "$API_HOST_PORT" != "8000" ]; then
  echo "Host port 8000 is busy; using API host port $API_HOST_PORT instead." >&2
fi
export API_HOST_PORT

if ! WEB_HOST_PORT="$(resolve_host_port WEB_HOST_PORT web 3000 3000 3010)"; then
  echo "Host ports 3000-3010 are all busy; stop one or set WEB_HOST_PORT manually." >&2
  exit 1
fi
if [ -z "$web_port_supplied" ] && [ -z "$web_existing_port" ] && [ "$WEB_HOST_PORT" != "3000" ]; then
  echo "Host port 3000 is busy; using web host port $WEB_HOST_PORT instead." >&2
fi
export WEB_HOST_PORT

print_context() {
  echo "Compose project: $COMPOSE_PROJECT_NAME" >&2
  echo "Host ports: Postgres $POSTGRES_HOST_PORT, API $API_HOST_PORT, Web $WEB_HOST_PORT" >&2
}

report_failure() {
  local failed_service="$1"
  echo "Quickstart failed for Compose project '$COMPOSE_PROJECT_NAME'." >&2
  print_context
  compose ps >&2 || true
  if [ "$failed_service" = "startup" ]; then
    for service in postgres schema api seed web; do
      echo "--- recent $service logs ---" >&2
      compose logs --tail=50 "$service" >&2 || true
    done
  else
    echo "--- recent $failed_service logs ---" >&2
    compose logs --tail=50 "$failed_service" >&2 || true
  fi
}

echo "Docker is ready. Starting GovernedMemory..."
if ! compose --profile seed up --build -d; then
  report_failure startup
  exit 1
fi

api_ready() {
  if command -v curl >/dev/null 2>&1; then
    curl --fail --silent --show-error "http://127.0.0.1:${API_HOST_PORT}/healthz" >/dev/null 2>&1
  else
    compose exec -T api \
      python -c 'import urllib.request; urllib.request.urlopen("http://localhost:8000/healthz", timeout=2)' \
      >/dev/null 2>&1
  fi
}

web_ready() {
  if command -v curl >/dev/null 2>&1; then
    curl --fail --silent --show-error --output /dev/null "http://127.0.0.1:${WEB_HOST_PORT}"
  else
    compose exec -T web \
      node -e 'fetch("http://localhost:3000").then(r => process.exit(r.status < 500 ? 0 : 1)).catch(() => process.exit(1))' \
      >/dev/null 2>&1
  fi
}

echo "Waiting for the demo seed and application health..."
seed_container=""
for _ in $(seq 1 60); do
  seed_container="$(compose ps -aq seed 2>/dev/null | head -n 1 || true)"
  if [ -n "$seed_container" ]; then
    seed_state="$(docker inspect -f '{{.State.Status}} {{.State.ExitCode}}' "$seed_container" 2>/dev/null || true)"
    case "$seed_state" in
      "exited 0") break ;;
      exited\ *)
        echo "The demo seed failed ($seed_state)." >&2
        report_failure seed
        exit 1
        ;;
    esac
  fi
  sleep 1
done

if [ -z "$seed_container" ] || [ "$(docker inspect -f '{{.State.Status}} {{.State.ExitCode}}' "$seed_container" 2>/dev/null || true)" != "exited 0" ]; then
  echo "The demo seed did not finish within 60 seconds." >&2
  report_failure seed
  exit 1
fi

api_ok=0
web_ok=0
for _ in $(seq 1 60); do
  if [ "$api_ok" -eq 0 ] && api_ready; then api_ok=1; fi
  if [ "$web_ok" -eq 0 ] && web_ready; then web_ok=1; fi
  [ "$api_ok" -eq 1 ] && [ "$web_ok" -eq 1 ] && break
  sleep 1
done

if [ "$api_ok" -ne 1 ]; then
  echo "The API did not become ready within 60 seconds." >&2
  report_failure api
  exit 1
fi
if [ "$web_ok" -ne 1 ]; then
  echo "The web console did not become ready within 60 seconds." >&2
  report_failure web
  exit 1
fi

if [ -t 1 ] && [ -z "${NO_COLOR:-}" ]; then
  bold_green=$'\033[1;32m'
  bold_cyan=$'\033[1;36m'
  bold=$'\033[1m'
  reset=$'\033[0m'
  osc8_start=$'\033]8;;'
  osc8_end=$'\033]8;;\033\\'
else
  bold_green=""
  bold_cyan=""
  bold=""
  reset=""
  osc8_start=""
  osc8_end=""
fi

print_link() {
  local url="$1"
  local label="${2:-$url}"
  if [ -n "$osc8_start" ]; then
    printf '%s%s%s%s%s\n' "$osc8_start" "$url" $'\033\\' "$bold_cyan$label$reset" "$osc8_end"
  else
    printf '%s%s%s\n' "$bold_cyan" "$label" "$reset"
  fi
}

printf '\n%sGovernedMemory is ready.%s\n\n' "$bold_green" "$reset"
printf '%sWeb console:%s ' "$bold" "$reset"
print_link "http://localhost:${WEB_HOST_PORT}"
printf '%sAPI health:%s  ' "$bold" "$reset"
print_link "http://localhost:${API_HOST_PORT}/healthz"
printf '\n%sNext steps:%s\n' "$bold" "$reset"
printf '1. Open the web console.\n'
printf '2. Go to %sWrite%s.\n' "$bold_cyan" "$reset"
printf '3. Submit the example injection text from the README.\n'
printf '4. Open %sAudit Log%s to inspect the blocked event.\n' "$bold_cyan" "$reset"
