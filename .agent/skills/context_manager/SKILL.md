---
name: Context Manager
description: Persistent memory system for the agent to store and retrieve context, preferences, and architectural decisions across sessions.
---

# Context Manager Skill

This skill allows the agent to store and retrieve information from a persistent SQLite database. This "memory" is useful for keeping track of user preferences, architectural patterns, decision logs, and active task states across different chats and days.

## Capabilities

1.  **Remember**: Store a new piece of information with a category and tags.
2.  **Recall**: Search for information using full-text search or filter by category.

## usage

### Python Scripts

The core logic resides in `scripts/memory_db.py`.
Convenience wrappers are provided:

-   `scripts/remember.py`: Add a memory.
-   `scripts/recall.py`: Search memories.

### Examples

**Adding a Memory:**
```bash
python scripts/remember.py --category "preference" --content "User prefers Tailwind CSS for all new web projects." --tags "css,ui,frontend"
```

**Recalling a Memory:**
```bash
python scripts/recall.py --query "Tailwind"
# Or by category
python scripts/recall.py --category "preference"
```

## Database Schema

The database is located at `.agent/memory.db`.

Table `memories`:
- `id`: INTEGER PRIMARY KEY
- `category`: TEXT
- `content`: TEXT
- `tags`: TEXT
- `created_at`: DATETIME
- `updated_at`: DATETIME
