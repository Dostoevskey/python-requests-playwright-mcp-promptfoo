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
--reset          Remove installed node_modules to force a clean install
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
  echo "Bundled demo app not found at $TARGET_DIR" >&2
  echo "The repository vendors the RealWorld example app. Restore the directory from source control." >&2
  exit 1
fi

if [[ ${RESET} -eq 1 ]]; then
  echo "Resetting demo app dependencies"
  rm -rf \
    "$TARGET_DIR/node_modules" \
    "$TARGET_DIR/backend/node_modules" \
    "$TARGET_DIR/frontend/node_modules" \
    "$TARGET_DIR/frontend/.vite"
fi

if ! command -v npm >/dev/null 2>&1; then
  echo "npm is required to install demo app dependencies." >&2
  exit 1
fi

pushd "$TARGET_DIR" >/dev/null

echo "Installing npm workspaces..."
PLAYWRIGHT_SKIP_VALIDATE_HOST_REQUIREMENTS=1 npm install --prefer-offline --no-fund

DB_STORAGE_PATH=${DB_STORAGE:-$ROOT_DIR/demo-app/realworld.sqlite}
DB_DIALECT="${DB_DIALECT:-sqlite}"

if [[ "$DB_DIALECT" == "sqlite" ]]; then
  if [[ "$DB_STORAGE_PATH" != /* ]]; then
    DB_STORAGE_PATH="$ROOT_DIR/${DB_STORAGE_PATH#./}"
  fi
  mkdir -p "$(dirname "$DB_STORAGE_PATH")"
fi

cat <<ENV > backend/.env
PORT=${API_PORT:-3001}
JWT_KEY=${JWT_KEY:-supersecretkey}
SEQUELIZE_SYNC_MODE=${SEQUELIZE_SYNC_MODE:-skip}

DEV_DB_USERNAME=${DB_USER}
DEV_DB_PASSWORD=${DB_PASSWORD}
DEV_DB_NAME=${DB_NAME}
DEV_DB_HOSTNAME=${DB_HOST}
DEV_DB_DIALECT=${DB_DIALECT}
DEV_DB_STORAGE=${DB_STORAGE_PATH}
DEV_DB_LOGGING=false

TEST_DB_USERNAME=${DB_USER}
TEST_DB_PASSWORD=${DB_PASSWORD}
TEST_DB_NAME=${DB_NAME}_test
TEST_DB_HOSTNAME=${DB_HOST}
TEST_DB_DIALECT=${DB_DIALECT}
TEST_DB_STORAGE=${DB_STORAGE_PATH}
TEST_DB_LOGGING=false

PROD_DB_USERNAME=${DB_USER}
PROD_DB_PASSWORD=${DB_PASSWORD}
PROD_DB_NAME=${DB_NAME}_prod
PROD_DB_HOSTNAME=${DB_HOST}
PROD_DB_DIALECT=${DB_DIALECT}
PROD_DB_STORAGE=${DB_STORAGE_PATH}
PROD_DB_LOGGING=false
ENV

if [[ "$DB_DIALECT" == "sqlite" ]]; then
  echo "Using SQLite storage at ${DB_STORAGE_PATH}"
  npx -w backend sequelize-cli db:migrate --env development
else
  if ! command -v psql >/dev/null 2>&1; then
    echo "psql not found; ensure PostgreSQL client tools are installed before continuing." >&2
  fi
  npm run sqlz -- db:create || true
  npm run sqlz -- db:migrate
fi

popd >/dev/null

echo "Demo app bootstrap complete. Start the app with:"
echo "  (cd demo-app/src && npm run dev)"
