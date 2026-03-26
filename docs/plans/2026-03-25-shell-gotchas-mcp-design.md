# Shell Gotchas MCP Strategy

## Goal
Reduce token usage and development friction by centralizing verified terminal commands and environment quirks in the MCP "Second Brain".

## Problem
In windows/powershell environments, the AI frequently makes syntax errors (e.g., using `curl` as an interactive alias) or path-related mistakes. Each failure leads to a retry cycle that burns context tokens and wastes time.

## Proposed Solution: The Shell Memory Loop

### 1. The `Shell` Category
A dedicated category in `memory.db` for storing environment-specific terminal logic. 

**Structure**:
- **Topic**: The base command or intent (e.g., `curl`, `git rm`, `pathing`).
- **Content**: The "Verified Snippet" that works on this machine.
- **Metadata**: JSON containing specific os-version info if needed.

### 2. Operational Workflow
- **Pre-Flight**: AI checks `query_memory("Shell")` before running non-trivial terminal commands.
- **Auto-Update**: After any successful "fix" of a failed shell command, the AI MUST store the fix in memory to prevent recursion.

## Success Criteria
- [ ] 90% reduction in PowerShell syntax errors over time.
- [ ] Elimination of interactive prompt hangs (e.g., from `Invoke-WebRequest`).
- [ ] Faster task execution by bypassing trial-and-error cycles.

## Implementation Steps
1. Seed the memory with known foundational gotchas (curl, git, paths).
2. Update the `DataBridge` bootstrap tool to include these.
3. Establish the "Pre-Flight" check as a standard operating procedure for the agent.
