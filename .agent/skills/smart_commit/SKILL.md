---
name: smart_commit
description: Automated, token-efficient single-command git staging and conventional committing. Use when user requests a git commit or when finalizing feature work.
applyTo: "**"
---

# Smart Commit Skill

Use this skill whenever the user requests a git commit or when completing a feature to minimize token overhead and execute staging + conventional commits in a single fast command.

## When to use

Use when the user wants to commit changes — automated, token-efficient single-command git staging and conventional commit messages.

## Instructions

Instead of running multiple sequential tool calls (`git status`, `git diff`, `git add`, `git commit`), execute a single command using `smart_commit.py`:

```powershell
.\.venv\Scripts\python.exe -m scripts.utils.smart_commit -m "<message>" -s <scope> --type <type>
```

### Examples:

1. **Feature Commit with Scope**:
   ```powershell
   .\.venv\Scripts\python.exe -m scripts.utils.smart_commit -m "add pluggable data provider with schwab fallback" -s screener -t feat
   ```

2. **Bugfix Commit**:
   ```powershell
   .\.venv\Scripts\python.exe -m scripts.utils.smart_commit -m "fix case-insensitive column handling in data_policy" -s screener -t fix
   ```

3. **Auto-Inferred Staging & Message**:
   ```powershell
   .\.venv\Scripts\python.exe -m scripts.utils.smart_commit
   ```

### Benefits:
- Automatically ignores `__pycache__`, `.pytest_cache`, `scratch/`, `obj/`, and temporary build artifacts.
- Infers conventional commit formatting `feat(scope): message` automatically.
- Reduces token window usage by >90% per commit operation.
