---
name: Documentation Architect
description: Automatically creates and updates design/architecture documentation when entering new code areas.
---

# Documentation Architect

## Purpose
Ensures that every major component of the codebase has a corresponding design document in `docs/architecture/` or relevant subfolders. It prevents "knowledge rot" by mandating updates whenever significant changes occur.

## Triggers
Activate this skill when:
1.  Starting work on a new feature or component.
2.  Refactoring an existing component.
3.  Entering a code area that lacks documentation.
4.  Completing a task that altered the system architecture.

## Workflow

### 1. Assessment
- **Identify** the scope (e.g., "Live Chart", "Backtest Engine").
- **Search** `docs/` for existing relevant files.
    - Use `find_by_name` or `grep_search` to look for keyswords.
- **Check** if the existing docs match the current reality.

### 2. Creation (If Missing)
- **Create** a new file in `docs/architecture/[COMPONENT_NAME].md`.
- **Use Template**:
    ```markdown
    # [Component Name] Architecture

    ## 1. Overview
    [Brief description of purpose]

    ## 2. Key Responsibilities
    - [Responsibility 1]
    - [Responsibility 2]

    ## 3. Data Flow
    [Source] -> [Process] -> [Destination]

    ## 4. Key Components
    - **[File/Class]**: [Role]

    ## 5. Technology & Constraints
    - [Dependencies, constraints, performance targets]
    ```

### 3. Visuals & Diagrams
- **Mandatory**: Every architecture doc MUST include at least one Mermaid diagram explaining the data flow or component interaction.
- **Tools**: Use `mermaid` code blocks.
- **Example**:
    ```mermaid
    graph TD;
      Source-->Processor;
      Processor-->Storage;
    ```

### 4. Update (If Exists)
- **Read** the existing file.
- **Compare** with the new implementation.
- **Update** sections like "Data Flow" or "Key Components" to reflect changes.
- **Add** a "Changelog" or "Version History" note if appropriate, or simply overwrite outdated info.

### 4. Verification
- **Verify** that the document accurately describes the *current* state, not the *previous* state.
