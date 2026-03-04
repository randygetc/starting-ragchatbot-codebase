# Frontend Changes: Dark/Light Theme Toggle

## Overview
Added a dark/light theme toggle button to the chat UI. Users can switch between themes at any time; their preference is persisted in `localStorage`.

---

## Files Modified

### `frontend/index.html`
- Bumped CSS cache-buster: `style.css?v=11` → `style.css?v=12`
- Bumped JS cache-buster: `script.js?v=10` → `script.js?v=11`
- Added a fixed-position `<button id="themeToggle" class="theme-toggle">` at the top of `<body>` (before `.container`), containing:
  - A **moon SVG** (`.icon-moon`) — visible in dark mode
  - A **sun SVG** (`.icon-sun`) — visible in light mode
  - `aria-label="Toggle light/dark theme"` and `title="Toggle theme"` for accessibility

### `frontend/style.css`
1. **New CSS variable `--code-bg`** added to `:root` (`rgba(0,0,0,0.2)`) and used in `.message-content code` and `.message-content pre` instead of hardcoded values.

2. **Light theme block** `[data-theme="light"]` overrides all design-token variables:
   | Variable | Light value |
   |---|---|
   | `--background` | `#f8fafc` |
   | `--surface` | `#ffffff` |
   | `--surface-hover` | `#f1f5f9` |
   | `--text-primary` | `#0f172a` |
   | `--text-secondary` | `#64748b` |
   | `--border-color` | `#e2e8f0` |
   | `--shadow` | `0 4px 6px -1px rgba(0,0,0,0.1)` |
   | `--welcome-bg` | `#eff6ff` |
   | `--code-bg` | `rgba(0,0,0,0.05)` |
   Primary/accent colors remain the same as dark mode.

3. **Smooth transition helper** — `html.theme-transitioning` (and all its descendants) gets a 0.3 s ease transition on `background-color`, `color`, `border-color`, and `box-shadow` via `!important`. The class is added/removed by JavaScript around every theme switch.

4. **`.theme-toggle` styles** — fixed `40×40 px` circular button, top-right corner (`top: 1rem; right: 1rem; z-index: 100`). Hover lifts the button with `translateY(-1px)` and applies `--primary-color` tint. Focus shows a `--focus-ring` outline.

5. **Icon show/hide logic** via CSS:
   - Default (dark): `.icon-moon` visible, `.icon-sun` rotated and invisible.
   - `[data-theme="light"]`: `.icon-sun` visible, `.icon-moon` rotated and invisible.
   Icons cross-fade with a 0.2 s opacity + rotation transition.

### `frontend/script.js`
- **`initTheme()`** — reads `localStorage.getItem('theme')` (defaults to `'dark'`) and sets `document.documentElement.setAttribute('data-theme', savedTheme)`. Called immediately (before `DOMContentLoaded`) to prevent flash of wrong theme.
- **`toggleTheme()`** — reads current `data-theme`, flips to the other value, saves to `localStorage`, and temporarily adds/removes `theme-transitioning` class on `<html>` for the smooth CSS transition.
- **Event listener** for `#themeToggle` wired up inside `setupEventListeners()`.
