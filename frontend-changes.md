# Frontend Changes: Code Quality Tooling

## Overview

Added code quality tooling for the frontend (HTML, CSS, JavaScript). The frontend is vanilla JS/HTML/CSS with no build system, so lightweight tools were chosen that work without a bundler.

## New Files

### `frontend/package.json`
Introduces npm-based dev tooling for the frontend. Contains:
- **devDependencies**: `prettier`, `eslint`, `eslint-config-prettier`
- **scripts**:
  - `format` — auto-format all JS/CSS/HTML files with Prettier
  - `format:check` — check formatting without modifying files (for CI)
  - `lint` — run ESLint on all JS files
  - `check` — run both lint and format:check (full quality gate)

### `frontend/.prettierrc`
Prettier configuration enforcing consistent formatting across JS, CSS, and HTML:
- 4-space indentation (matches existing codebase style)
- Single quotes for JS strings
- Semicolons required
- `es5` trailing commas
- 80-character print width

### `frontend/.eslintrc.js`
ESLint configuration for vanilla browser JavaScript:
- `eslint:recommended` ruleset as the base
- `prettier` config to disable rules that conflict with Prettier
- `marked` declared as a global (CDN dependency)
- `no-unused-vars`: warn
- `no-console`: warn
- `no-multiple-empty-lines`: error (max 1 blank line between blocks)

### `scripts/check-frontend.sh`
Shell script for running all frontend quality checks in one command:
```bash
./scripts/check-frontend.sh
```
Installs `node_modules` automatically if missing, then runs ESLint and Prettier checks. Exits non-zero on any failure, suitable for use in CI pipelines.

## Modified Files

### `frontend/script.js`
Applied formatting consistency fixes:
- Removed double blank line inside `setupEventListeners()` (between the `keypress` listener and the new chat button listener)
- Removed double blank line between `setupEventListeners()` and `sendMessage()` function definitions
- Removed trailing whitespace after `courseTitles` assignment in the `DOMContentLoaded` callback

## Usage

Install dependencies once (requires Node.js/npm):
```bash
cd frontend
npm install
```

Run all quality checks:
```bash
./scripts/check-frontend.sh
# or from frontend/ directly:
npm run check
```

Auto-format all frontend files:
```bash
cd frontend
npm run format
```
