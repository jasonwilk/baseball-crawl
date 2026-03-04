#!/bin/bash
# scripts/install-hooks.sh
# Run this once after cloning the repository.
# Sets up the Git pre-commit hook for PII scanning.

set -e

REPO_ROOT="$(git rev-parse --show-toplevel)"

echo "Configuring Git to use .githooks/ directory..."
git config core.hooksPath .githooks

echo "Verifying hook is executable..."
chmod +x "$REPO_ROOT/.githooks/pre-commit"

echo "Done. PII pre-commit hook is active."
echo "Test it with: git commit --allow-empty -m 'test hook'"
