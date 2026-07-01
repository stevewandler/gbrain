#!/bin/bash
# G-Brain Railway Production Startup Recovery
# Runs on service start to clear supervisor wedges and dead jobs
# This prevents manual SSH intervention needs

set -e

echo "[STARTUP] G-Brain Recovery: supervisor wedge + dead jobs cleanup"

# Add node/bun binaries to PATH (handles postinstall PATH issues)
export PATH="/app/node_modules/.bin:/root/.bun/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:$PATH"

cd /app

# Build the binary if it doesn't exist or is stale
if [ ! -f bin/gbrain ] || [ ! -x bin/gbrain ]; then
  echo "[STARTUP] Building gbrain binary..."
  bun run build
fi

# Wait for database to be ready (Railway Postgres may still be initializing)
echo "[STARTUP] Waiting for database availability..."
MAX_RETRIES=30
RETRY=0
until [ $RETRY -ge $MAX_RETRIES ]; do
  if timeout 5 psql "$DATABASE_URL" -t -c "SELECT 1;" >/dev/null 2>&1; then
    echo "[STARTUP] Database is ready"
    break
  fi
  RETRY=$((RETRY + 1))
  echo "[STARTUP] Database not ready, retry $RETRY/$MAX_RETRIES..."
  sleep 2
done

# Clean dead/cancelled jobs to prevent supervisor drowning
echo "[STARTUP] Cleaning dead job queue..."
timeout 10 psql "$DATABASE_URL" -t -c "
  DELETE FROM minions_jobs_all 
  WHERE status IN ('cancelled', 'failed', 'dead')
  OR (status = 'waiting' AND created_at < NOW() - INTERVAL '72 hours');
" 2>/dev/null || echo "[STARTUP] Job cleanup failed (non-critical)"

# Restart supervisor to clear any wedges
echo "[STARTUP] Restarting supervisor..."
bin/gbrain jobs supervisor stop 2>/dev/null || true
sleep 2
bin/gbrain jobs supervisor start

# Verify supervisor came back
echo "[STARTUP] Verifying supervisor..."
bin/gbrain jobs supervisor status

echo "[STARTUP] Recovery complete. GBrain service ready to start."
