#!/bin/bash
set -euo pipefail

REPO="/Users/stevewandler/github-repos/gbrain"
LOG="$REPO/gbrain-update-local.log"
BINARY="$REPO/gbrain"

exec >> "$LOG" 2>&1
echo "=== $(date -Iseconds) ==="

cd "$REPO"

BEFORE=$(cat VERSION 2>/dev/null || echo "unknown")

git fetch upstream --quiet
LOCAL=$(git rev-parse HEAD)
REMOTE=$(git rev-parse upstream/master)

if [ "$LOCAL" = "$REMOTE" ]; then
  echo "Already at latest ($BEFORE). Nothing to do."
  exit 0
fi

echo "Updating from $BEFORE..."

# Use -B to create-or-reset the branch (avoids "already exists" error)
git checkout -B upstream-latest upstream/master --quiet
git reset --hard upstream/master --quiet

bun install --frozen-lockfile 2>/dev/null || bun install
bun build src/cli.ts --compile --outfile "$BINARY"

AFTER=$(cat VERSION 2>/dev/null || echo "unknown")
echo "Updated: $BEFORE → $AFTER"

"$BINARY" --version
echo "=== done ==="
