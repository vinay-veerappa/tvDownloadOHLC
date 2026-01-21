---
name: Git Snapshot
description: Stages relevant documentation and scripts, creating a commit with a timestamped or user-provided message.
---

# Git Snapshot

This skill captures the current state of analysis and documentation.

## Workflow Steps

1.  **Stage Core Directories**
    We intentionally verify what we are adding to avoid committing large data files (though `.gitignore` should handle this).

    ```powershell
    git add docs/DailyClassification/
    git add scripts/analysis/
    git add scripts/derived/
    # Add other doc folders if relevant
    git add docs/
    ```

2.  **Commit**
    Commit with a clear message.

    ```powershell
    # Usage: Provide a message or default to "Update Analysis"
    git commit -m "Snapshot: Market Analysis Update"
    ```

3.  **Status Check**
    Verify the state execution.

    ```powershell
    git status
    ```
