---
name: Code Guardian
description: Enforces code quality, checks for lint errors, and validates types before specialized tasks.
applyTo: "**"
---

# Code Guardian

## When to use

Use before running tests or committing code — enforces code quality by checking for lint errors, type validation, and common pitfalls before executing specialized workflows.

## Purpose
Acts as the Quality Assurance gatekeeper. Ensures that code changes do not break the build or introduce regressions.

## Triggers
- Before running `git commit`.
- After significant refactoring.
- When creating new React components or Python scripts.

## Workflow

### 1. Frontend Check (Next.js)
- **Lint**: Run `npm run lint` in `web/`.
- **Type Check**: Verify no critical `tsc` errors (implicit in lint or build).
- **Config**: Ensure `next.config.ts`, `tailwind.config.ts`, and `package.json` are valid.

### 2. Backend Check (Python)
- **Syntax**: Ensure scripts can be parsed.
- **Dependencies**: Check if imports match `requirements.txt` or standard library.
- **Paths**: Verify relative paths logic (e.g., using `Path(__file__).parent`) so scripts run from any CWD.

### 3. Safety Guidelines
- **No Force Pushing**: Protect main branch history.
- **Secrets**: Scan for accidental API key inclusion.
