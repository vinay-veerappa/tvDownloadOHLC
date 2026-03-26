# Token Efficiency & AI-Native Roadmap

## Goal
Optimize the interaction between the AI and the codebase to minimize token usage, reduce latency, and eliminate redundant discovery cycles.

## 1. Environment & Shell (Priority: High)
**Status**: Seeding
- **Shell Gotchas Category**: Store verified Windows/PowerShell snippets in MCP Memory.
- **Goal**: Zero failed terminal commands due to syntax or platform quirks.

## 2. Data Context (Priority: High)
**Status**: Planned
- **Data Cards**: Store metadata for all Parquet sources in MCP Memory.
- **Goal**: Know Schema, Timezone, and Frequency without opening files.
- **Example**: `query_memory("NQ1_Data_Card")` returns the field list and session times.

## 3. Schema & Logic Context (Priority: Medium)
**Status**: Planned
- **Model Cards**: Store Prisma model definitions and their specific "Purpose/Usage" descriptions.
- **Goal**: Get a 10-line field summary instead of reading a 300-line `schema.prisma`.

## 4. Web Knowledge Caching (Priority: Medium)
**Status**: Planned
- **Research Summaries**: Store "Dense Summaries" of GitHub issues, Reddit fixes, or Library documentation in MCP Memory.
- **Goal**: Only "buy" the tokens for a web research task once per project.

## 5. Architectural Memory (Priority: Low)
**Status**: Ongoing
- **Toolset ADRs**: Use the **Second Brain** as the source of truth for "Why we use X over Y."
- **Goal**: Eliminate persistent architectural resets and re-justification in new sessions.

## Execution Pattern
For every new discovery (a library fix, a data schema change, a shell quirk), the agent's first step is to **update the Second Brain** via the MCP `add_memory` tool.
