#!/usr/bin/env bash
# Test harness for .github/scripts/safe_push.sh.
#
# Why a shell test: safe_push.sh is bash that orchestrates real git plumbing.
# Mocking that in Python adds noise; spinning up a couple of local bare repos
# and asserting on the resulting refs is the highest-fidelity check.
#
# Run via pytest (test_safe_push.py wraps this) or directly:
#   bash tests/test_safe_push.sh

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SAFE_PUSH="$REPO_ROOT/.github/scripts/safe_push.sh"

if [ ! -x "$SAFE_PUSH" ]; then
  echo "FAIL: $SAFE_PUSH is not executable"
  exit 1
fi

WORKDIR="$(mktemp -d)"
trap 'rm -rf "$WORKDIR"' EXIT

# Quiet git, deterministic identity, no parent config leakage.
export GIT_CONFIG_GLOBAL=/dev/null
export GIT_CONFIG_SYSTEM=/dev/null
export GIT_AUTHOR_NAME=test
export GIT_AUTHOR_EMAIL=test@example.com
export GIT_COMMITTER_NAME=test
export GIT_COMMITTER_EMAIL=test@example.com

setup_remote() {
  local name="$1"
  git init --quiet --bare --initial-branch=main "$WORKDIR/$name.git"
  echo "$WORKDIR/$name.git"
}

setup_clone() {
  local remote="$1"
  local name="$2"
  git clone --quiet "$remote" "$WORKDIR/$name" 2>/dev/null
  (
    cd "$WORKDIR/$name"
    git symbolic-ref HEAD refs/heads/main
    echo "seed" > seed.txt
    git add seed.txt
    git commit --quiet -m "seed"
    git push --quiet origin HEAD:main
  )
}

assert() {
  local label="$1"
  local cond="$2"
  if eval "$cond"; then
    echo "PASS: $label"
  else
    echo "FAIL: $label  ($cond)"
    exit 1
  fi
}

# ──────────────────────────────────────────────────────────────────────────
# Case 1: clean working tree, no concurrent push.
# Expectation: push succeeds, remote HEAD matches local.
# ──────────────────────────────────────────────────────────────────────────
case_clean() {
  local remote
  remote=$(setup_remote "clean")
  setup_clone "$remote" "clean-work"
  cd "$WORKDIR/clean-work"
  echo "round-5" > round_05.json
  git add round_05.json
  git commit --quiet -m "round 5"
  bash "$SAFE_PUSH" >/dev/null
  local local_sha remote_sha
  local_sha=$(git rev-parse HEAD)
  remote_sha=$(git --git-dir="$remote" rev-parse main)
  assert "clean tree: remote matches local" "[ \"$local_sha\" = \"$remote_sha\" ]"
}

# ──────────────────────────────────────────────────────────────────────────
# Case 2: leftover unstaged tracked-file modification after the curated commit.
# This is the exact scenario that broke production: gp_weekend.py overwrites
# models/registry/<round>/metadata.json, the workflow commits only website
# data, the rebase pre-check then aborts on the unstaged tracked file.
# Expectation: safe_push.sh stashes it, rebases, pushes.
# ──────────────────────────────────────────────────────────────────────────
case_unstaged_tracked() {
  local remote
  remote=$(setup_remote "unstaged")
  setup_clone "$remote" "unstaged-work"
  cd "$WORKDIR/unstaged-work"
  # Seed the tracked file the pipeline will later modify.
  mkdir -p models/registry/2026_round_05
  echo '{"kind":"qualifying-time","seed":true}' > models/registry/2026_round_05/metadata.json
  git add models/registry/2026_round_05/metadata.json
  git commit --quiet -m "seed registry"
  git push --quiet origin HEAD:main
  # Now simulate a pipeline run: stage + commit website data, leave the
  # registry metadata modified-but-unstaged.
  echo "round-5" > round_05.json
  echo '{"kind":"qualifying-time","seed":false,"regenerated":true}' > models/registry/2026_round_05/metadata.json
  git add round_05.json
  git commit --quiet -m "curated commit"
  # Sanity: the modified registry file IS unstaged at this point.
  if git diff --quiet; then
    echo "FAIL: precondition — expected unstaged modification"
    exit 1
  fi
  bash "$SAFE_PUSH" >/dev/null
  local local_sha remote_sha
  local_sha=$(git rev-parse HEAD)
  remote_sha=$(git --git-dir="$remote" rev-parse main)
  assert "unstaged tracked change: remote matches local" "[ \"$local_sha\" = \"$remote_sha\" ]"
}

# ──────────────────────────────────────────────────────────────────────────
# Case 3: concurrent push to main between local commit and our push.
# Expectation: safe_push fetches, rebases onto the new tip, and pushes.
# ──────────────────────────────────────────────────────────────────────────
case_concurrent_push() {
  local remote
  remote=$(setup_remote "concurrent")
  setup_clone "$remote" "concurrent-work"
  # Second clone simulates the other workflow racing us.
  git clone --quiet --branch main "$remote" "$WORKDIR/concurrent-other"
  cd "$WORKDIR/concurrent-other"
  echo "other" > other.txt
  git add other.txt
  git commit --quiet -m "concurrent push from other workflow"
  git push --quiet origin HEAD:main
  cd "$WORKDIR/concurrent-work"
  echo "round-5" > round_05.json
  git add round_05.json
  git commit --quiet -m "our curated commit"
  bash "$SAFE_PUSH" >/dev/null
  # Remote tip is now our commit; its parent is the concurrent commit.
  local remote_sha parent_sha
  remote_sha=$(git --git-dir="$remote" rev-parse main)
  parent_sha=$(git --git-dir="$remote" rev-parse "main^")
  assert "concurrent push: remote tip is our commit" "[ \"$remote_sha\" = \"$(git rev-parse HEAD)\" ]"
  assert "concurrent push: rebased onto concurrent commit" "git --git-dir=\"$remote\" log --format=%s \"$parent_sha\" -n1 | grep -q 'concurrent push'"
}

# ──────────────────────────────────────────────────────────────────────────
# Case 4: leftover untracked files in working tree.
# Expectation: untracked files do not block rebase, push succeeds.
# ──────────────────────────────────────────────────────────────────────────
case_untracked() {
  local remote
  remote=$(setup_remote "untracked")
  setup_clone "$remote" "untracked-work"
  cd "$WORKDIR/untracked-work"
  echo "round-5" > round_05.json
  git add round_05.json
  git commit --quiet -m "curated commit"
  # Drop in an untracked artefact the pipeline might produce.
  echo "scratch" > scratch.tmp
  bash "$SAFE_PUSH" >/dev/null
  local remote_sha
  remote_sha=$(git --git-dir="$remote" rev-parse main)
  assert "untracked artefacts: push succeeds" "[ \"$(git rev-parse HEAD)\" = \"$remote_sha\" ]"
}

case_clean
case_unstaged_tracked
case_concurrent_push
case_untracked

echo
echo "All safe_push.sh scenarios passed."
