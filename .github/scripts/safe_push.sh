#!/usr/bin/env bash
# safe_push.sh — rebase-and-push helper for cron workflows.
#
# update_predictions.yml and backfill_history.yml both push to main on
# overlapping crons.  This helper retries the rebase + push up to N times,
# auto-stashing any leftover working-tree changes so the rebase pre-check
# does not abort with "You have unstaged changes" when the pipeline left
# behind tracked-file edits we did not include in the curated commit
# (e.g. models/registry/*/metadata.json overwritten by a re-train run).
#
# Inputs (env): TARGET_BRANCH (default: main), MAX_ATTEMPTS (default: 3).
# Exit codes: 0 on success, 1 if all attempts fail.

set -uo pipefail

TARGET_BRANCH="${TARGET_BRANCH:-main}"
MAX_ATTEMPTS="${MAX_ATTEMPTS:-3}"

# Park any leftover unstaged / untracked work so it does not block the
# rebase pre-check.  We drop the stash on success — the bot does not care
# about uncommitted state across runs.
STASH_TAG="safe-push-$$"
STASHED=0
if ! git diff --quiet || ! git diff --cached --quiet || [ -n "$(git ls-files --others --exclude-standard)" ]; then
  if git stash push --include-untracked --message "$STASH_TAG" --quiet; then
    STASHED=1
  fi
fi

cleanup_stash() {
  if [ "$STASHED" = "1" ]; then
    # Find and drop the stash by tag; ignore if already gone.
    local ref
    ref=$(git stash list | grep -F "$STASH_TAG" | head -n1 | cut -d: -f1 || true)
    if [ -n "$ref" ]; then
      git stash drop "$ref" >/dev/null 2>&1 || true
    fi
  fi
}
trap cleanup_stash EXIT

for attempt in $(seq 1 "$MAX_ATTEMPTS"); do
  if ! git fetch origin "$TARGET_BRANCH"; then
    echo "fetch failed (attempt $attempt)"
    sleep 5
    continue
  fi
  if ! git rebase "origin/$TARGET_BRANCH"; then
    git rebase --abort >/dev/null 2>&1 || true
    echo "rebase failed (attempt $attempt)"
    sleep 5
    continue
  fi
  if git push origin "HEAD:$TARGET_BRANCH"; then
    echo "push succeeded on attempt $attempt"
    exit 0
  fi
  echo "push failed on attempt $attempt; retrying"
  sleep $((attempt * 10))
done

echo "push failed after $MAX_ATTEMPTS attempts"
exit 1
