#!/usr/bin/env bash
# Install qhaway's git hooks by pointing core.hooksPath at scripts/hooks.
# Idempotent; run from anywhere in the repo. Tracked hooks (versioned with the
# code) instead of copying into .git/hooks, so the discipline travels with clones.

set -euo pipefail

repo_root=$(git rev-parse --show-toplevel)
cd "$repo_root"

git config core.hooksPath scripts/hooks
chmod +x scripts/hooks/* 2>/dev/null || true

echo "qhaway hooks installed (core.hooksPath -> scripts/hooks)."
echo "Active: pre-commit (code/test separation, approach A)."
