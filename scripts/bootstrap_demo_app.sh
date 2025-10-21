#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
TARGET_DIR="$ROOT_DIR/demo-app/src"
CONFIG_FILE="$ROOT_DIR/config/demo.env"
RESET=0

usage() {
  cat <<USAGE
Usage: $0 [--env-file PATH] [--reset]

--env-file PATH  Load configuration overrides from PATH (defaults to config/demo.env)
--reset          Remove the existing demo app clone before re-cloning
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --env-file)
      CONFIG_FILE="$2"
      shift 2
      ;;
    --reset)
      RESET=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage
      exit 1
      ;;
  esac
done

if [[ ! -f "$CONFIG_FILE" ]]; then
  echo "Configuration file not found: $CONFIG_FILE" >&2
  exit 1
fi

# shellcheck disable=SC1090
source "$CONFIG_FILE"

if [[ ! -d "$TARGET_DIR" ]]; then
  echo "Bundled demo application not found at $TARGET_DIR" >&2
  echo "The project now vendors the Conduit RealWorld example app; restore the directory from source control." >&2
  exit 1
fi

if [[ ${RESET} -eq 1 ]]; then
  echo "Resetting demo app dependencies"
  rm -rf \
    "$TARGET_DIR/node_modules" \
    "$TARGET_DIR/backend/node_modules" \
    "$TARGET_DIR/frontend/node_modules"
fi

if ! command -v npm >/dev/null 2>&1; then
  echo "npm is required to install demo app dependencies." >&2
  exit 1
fi

pushd "$TARGET_DIR" >/dev/null

echo "Installing npm workspaces..."
npm install

echo "Preparing backend .env file"
cat <<ENV > backend/.env
PORT=${API_PORT:-3001}
JWT_KEY=${JWT_KEY:-supersecretkey}

DEV_DB_USERNAME=${DB_USER}
DEV_DB_PASSWORD=${DB_PASSWORD}
DEV_DB_NAME=${DB_NAME}
DEV_DB_HOSTNAME=${DB_HOST}
DEV_DB_DIALECT=postgres
DEV_DB_LOGGING=false

TEST_DB_USERNAME=${DB_USER}
TEST_DB_PASSWORD=${DB_PASSWORD}
TEST_DB_NAME=${DB_NAME}_test
TEST_DB_HOSTNAME=${DB_HOST}
TEST_DB_DIALECT=postgres
TEST_DB_LOGGING=false

PROD_DB_USERNAME=${DB_USER}
PROD_DB_PASSWORD=${DB_PASSWORD}
PROD_DB_NAME=${DB_NAME}_prod
PROD_DB_HOSTNAME=${DB_HOST}
PROD_DB_DIALECT=postgres
PROD_DB_LOGGING=false
ENV

if ! command -v psql >/dev/null 2>&1; then
  echo "psql not found; ensure PostgreSQL client tools are installed before continuing." >&2
fi

echo "Running database migrations"
npm run sqlz -- db:create || true
npm run sqlz -- db:migrate

popd >/dev/null

echo "Demo app bootstrap complete. Start the app with:"
echo "  (cd demo-app/src && npm run dev)"
