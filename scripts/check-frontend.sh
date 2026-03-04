#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FRONTEND_DIR="$SCRIPT_DIR/../frontend"

echo "Running frontend quality checks..."
echo ""

cd "$FRONTEND_DIR"

if ! command -v npm &>/dev/null; then
    echo "Error: npm is not installed. Please install Node.js to run frontend checks."
    exit 1
fi

if [ ! -d "node_modules" ]; then
    echo "Installing frontend dependencies..."
    npm install
    echo ""
fi

echo "Checking JavaScript with ESLint..."
npm run lint
echo ""

echo "Checking formatting with Prettier..."
npm run format:check
echo ""

echo "All frontend quality checks passed!"
