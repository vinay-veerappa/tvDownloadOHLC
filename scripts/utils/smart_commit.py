"""
smart_commit.py
===============
Token-efficient automated git staging and conventional commit utility.
Usage:
  python -m scripts.utils.smart_commit -m "add pluggable provider" -s screener
  python -m scripts.utils.smart_commit -f scripts/utils/smart_commit.py -m "add smart commit helper"
  python -m scripts.utils.smart_commit  (auto-detects changes, scope, type, and message)
"""
import os
import sys
import subprocess
import argparse
from pathlib import Path
from typing import List, Tuple, Dict, Optional

# Files/Directories to exclude from auto-staging
IGNORE_PATTERNS = [
    "__pycache__",
    ".pyc",
    ".pytest_cache",
    ".tmp",
    "obj/",
    "scratch/",
    "tmp/",
    "test.txt",
    "test2.txt",
    ".venv",
    ".vscode",
]


def run_git_cmd(args: List[str]) -> Tuple[int, str]:
    """Runs a git command and returns (exit_code, stdout_str)."""
    try:
        res = subprocess.run(
            ["git"] + args,
            capture_output=True,
            text=True,
            check=False
        )
        return res.returncode, res.stdout.strip()
    except Exception as e:
        return 1, str(e)


def normalize_path(p: str) -> str:
    return p.replace("\\", "/").strip("/").lower()


def get_changed_files(target_files: Optional[List[str]] = None) -> List[Tuple[str, str]]:
    """Returns list of tuples: (status_code, file_path)."""
    code, out = run_git_cmd(["status", "--porcelain"])
    if code != 0 or not out:
        return []
    
    changed = []
    target_norm = [normalize_path(t) for t in target_files] if target_files else None

    for line in out.splitlines():
        if len(line) < 3:
            continue
        status = line[:2].strip()
        fpath = line[2:].strip().strip('"')
        fpath_norm = normalize_path(fpath)
        
        # Filter target files if specified
        if target_norm and not any(t in fpath_norm or fpath_norm in t for t in target_norm):
            continue

        # Check ignores
        if any(ign in fpath for ign in IGNORE_PATTERNS):
            continue
            
        changed.append((status, fpath))
    return changed


def infer_scope_and_type(files: List[str]) -> Tuple[str, str]:
    """Infers conventional commit scope and type based on file paths."""
    scopes = []
    types = []

    for f in files:
        fl = f.lower()
        if "screener" in fl:
            scopes.append("screener")
        elif "options" in fl or "gex" in fl:
            scopes.append("options")
        elif "profiler" in fl:
            scopes.append("profiler")
        elif "trader" in fl or "narrative" in fl:
            scopes.append("trader")
        elif "ninjatrader" in fl:
            scopes.append("ninjatrader")
        elif "web/" in fl or "components/" in fl:
            scopes.append("ui")
        elif "api/" in fl:
            scopes.append("api")
        elif "docs/" in fl or fl.endswith(".md"):
            scopes.append("docs")
            types.append("docs")
        elif "tests/" in fl or "test_" in fl:
            types.append("test")

    # Determine primary scope
    scope = "core"
    if scopes:
        scope = max(set(scopes), key=scopes.count)

    # Determine primary type
    commit_type = "feat"
    if "test" in types and len(types) == len(files):
        commit_type = "test"
    elif "docs" in types and len(types) == len(files):
        commit_type = "docs"

    return scope, commit_type


def smart_commit(
    message: Optional[str] = None,
    scope: Optional[str] = None,
    commit_type: Optional[str] = None,
    dry_run: bool = False,
    files: Optional[List[str]] = None
) -> bool:
    """Executes token-efficient smart staging and committing."""
    changed = get_changed_files(files)
    if not changed:
        print("[smart_commit] No eligible changes found to commit.")
        return True

    file_paths = [f[1] for f in changed]
    
    # Infer scope and type if missing
    inferred_scope, inferred_type = infer_scope_and_type(file_paths)
    final_scope = scope or inferred_scope
    final_type = commit_type or inferred_type

    # Format commit message
    if message:
        clean_msg = message.strip()
        if not clean_msg.startswith(f"{final_type}(") and not clean_msg.startswith("feat:") and not clean_msg.startswith("fix:"):
            full_commit_msg = f"{final_type}({final_scope}): {clean_msg}"
        else:
            full_commit_msg = clean_msg
    else:
        file_summary = ", ".join([os.path.basename(f) for f in file_paths[:3]])
        if len(file_paths) > 3:
            file_summary += f" and {len(file_paths) - 3} more"
        full_commit_msg = f"{final_type}({final_scope}): update {file_summary}"

    print(f"[smart_commit] Scope: '{final_scope}' | Type: '{final_type}' | Files ({len(file_paths)}):")
    for status, fpath in changed[:10]:
        print(f"  {status:2s} {fpath}")
    if len(changed) > 10:
        print(f"  ... and {len(changed) - 10} more files.")

    print(f"\n[smart_commit] Message: \"{full_commit_msg}\"")

    if dry_run:
        print("[smart_commit] Dry run complete. No changes committed.")
        return True

    # 1. Stage files
    add_code, _ = run_git_cmd(["add"] + file_paths)
    if add_code != 0:
        print("[smart_commit] Error: Failed to stage files.")
        return False

    # 2. Commit
    commit_code, commit_out = run_git_cmd(["commit", "-m", full_commit_msg])
    if commit_code != 0:
        print(f"[smart_commit] Error during git commit:\n{commit_out}")
        return False

    # 3. Print clean 1-line summary
    rev_code, rev_out = run_git_cmd(["rev-parse", "--short", "HEAD"])
    sha = rev_out if rev_code == 0 else "UNKNOWN"
    print(f"\nSUCCESS: Committed [{sha}]: \"{full_commit_msg}\" ({len(file_paths)} files)")
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Smart automated git staging & conventional commit utility.")
    parser.add_argument("-m", "--message", type=str, default=None, help="Commit message description.")
    parser.add_argument("-s", "--scope", type=str, default=None, help="Conventional commit scope (e.g., screener, ui, options).")
    parser.add_argument("-t", "--type", type=str, default=None, help="Commit type (feat, fix, refactor, docs, test).")
    parser.add_argument("-f", "--files", nargs="*", default=None, help="Optional specific files to commit.")
    parser.add_argument("--dry-run", action="store_true", help="Preview staging and commit message without committing.")
    
    args = parser.parse_args()
    success = smart_commit(
        message=args.message,
        scope=args.scope,
        commit_type=args.type,
        dry_run=args.dry_run,
        files=args.files
    )
    sys.exit(0 if success else 1)
