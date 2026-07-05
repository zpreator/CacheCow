#!/usr/bin/env bash
# Polls origin/main and redeploys the docker compose stack when it moves.
# Intended to run on a schedule (e.g. cron) from within a git clone of this repo.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

LOCK_FILE="/tmp/cachecow-auto-deploy.lock"
exec 200>"$LOCK_FILE"
flock -n 200 || { echo "$(date -Iseconds) deploy already in progress, skipping"; exit 0; }

BRANCH="main"

git fetch --quiet origin "$BRANCH"

LOCAL=$(git rev-parse "$BRANCH")
REMOTE=$(git rev-parse "origin/$BRANCH")

if [ "$LOCAL" = "$REMOTE" ]; then
    exit 0
fi

echo "$(date -Iseconds) new commit on $BRANCH: $LOCAL -> $REMOTE, deploying..."

git checkout "$BRANCH" --quiet
git merge --ff-only "origin/$BRANCH"

docker compose build
docker compose up -d

echo "$(date -Iseconds) deploy complete: now at $(git rev-parse --short HEAD)"
