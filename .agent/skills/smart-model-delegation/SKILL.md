---
name: smart-model-delegation
description: Mandatory token-saving delegation protocol inside Antigravity. Automatically dispatches tasks to lower-token subagent models (flash_lite, flash) and local/cloud Ollama models.
---

# Smart Model Delegation Protocol (Antigravity Native)

Use this protocol during all development tasks to keep parent token consumption ultra-low while maintaining high reasoning quality.

## Core Rules

### 1. Delegating Research & Log Inspection (`flash_lite` / `flash`)
* **NEVER** read large log files (e.g. `pytest` outputs, server logs) or 10+ code files directly into the primary parent conversation context.
* **ALWAYS** dispatch a subagent using `invoke_subagent`:
  - **Task**: Single-file view, counting items, extracting log tracebacks -> `Model: "flash_lite"`
  - **Task**: Multi-file code search, feature auditing, running tests -> `Model: "flash"`
* Subagents process data in their own isolated background context windows and report back concise 3-line summaries to the primary parent context.

### 2. Zero-Cost Local & Cloud Model Delegation (`ollama_bridge`)
* For routine stubs, syntax checks, or isolated model queries, call the local/cloud Ollama router with `--output scratch/file.txt`:
  ```powershell
  # Save Ollama output directly to disk to prevent thousands of tokens entering parent context:
  .\.venv\Scripts\python.exe -m scripts.utils.ollama_bridge --model qwen3.6:latest --prompt "<task>" --output scratch/task_result.txt
  ```

### 3. Log & Test Output Piping
* Always pipe test suite runs and verbose outputs into log files (`> scratch/test.log`) and parse summaries rather than printing raw logs directly to terminal stdout.

### 4. Reserving High-Reasoning Models (`pro` / `inherit`)
* Reserve `pro` subagents or parent reasoning (`High` mode) strictly for high-ambiguity architecture decisions and complex multi-file trade math derivations.
