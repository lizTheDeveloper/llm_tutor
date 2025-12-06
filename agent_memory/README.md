# Agent Memory MCP Server

A Model Context Protocol (MCP) server that provides persistent, multi-layered memory capabilities for AI agents. Inspired by human memory systems and the "Inside Out" concept of core memories.

## Features

- **Core Memories**: Permanent personality principles and key learnings
- **Recent Memory**: Short-term working memory with auto-summarization (max 10 entries)
- **Current Task**: Track what the agent is actively working on
- **Episodic Memory**: Long-term storage of completed tasks and events
- **Memory Compost**: Archive of summarized memories

## Installation

```bash
cd agent-memory
pip install -r requirements.txt
```

## Configuration

Add to `.claude/mcp.json`:

```json
{
  "mcpServers": {
    "agent-memory": {
      "command": "python",
      "args": ["-m", "agent-memory.src.server"],
      "cwd": "/Users/annhoward/src/llm_tutor",
      "env": {
        "PYTHONPATH": "/Users/annhoward/src/llm_tutor",
        "ANTHROPIC_API_KEY": "${ANTHROPIC_API_KEY}"
      }
    }
  }
}
```

## Available Agents

- `tdd-implementer` - Test-Driven Development implementer
- `project-manager` - Project planning and coordination
- `value-chain-expert` - Business value and prioritization
- `product-requirements` - Requirements gathering and documentation

## MCP Tools

### Core Memory Management

- `add_core_memory(agent_id, memory)` - Add permanent core memory
- `get_core_memories(agent_id)` - Retrieve all core memories
- `delete_core_memory(agent_id, memory_id)` - Remove core memory

### Recent Memory Management

- `add_recent_memory(agent_id, memory)` - Add to recent memory (auto-summarizes at 10)
- `get_recent_memories(agent_id, limit=10)` - Get recent memories
- `clear_recent_memories(agent_id)` - Clear and summarize all recent memories

### Task Management

- `set_current_task(agent_id, task)` - Set/update current task
- `get_current_task(agent_id)` - Get current task

### Episodic Memory

- `add_episodic_memory(agent_id, memory, tags=None)` - Record completed event
- `search_episodic_memories(agent_id, keywords=None, from_date=None, to_date=None, limit=50)` - Search episodes

### Summary

- `get_memory_summary(agent_id)` - Get overview of all memory layers

## Memory Format

All memories should be **single sentences** that capture the essence of the information.

### Examples

**Core Memory:**
```
Always use raw SQL over SQLAlchemy for database queries
```

**Recent Memory:**
```
Implemented user authentication with OAuth2 flow
```

**Current Task:**
```
Refactoring the database connection pooling logic
```

**Episodic Memory:**
```
Completed integration of Stripe payment processing with webhook handling
```

## Auto-Summarization

When recent memory reaches 10 entries, the system automatically:
1. Collects all 10 memories
2. Uses Claude to generate a 1-2 sentence summary
3. Stores summary in Memory Compost
4. Clears recent memory for new entries

## Database

Uses SQLite (`agent_memory.db`) with the following tables:
- `core_memories` - Permanent principles
- `recent_memories` - Short-term working memory
- `current_task` - Active task tracking
- `episodic_memories` - Historical events
- `memory_compost` - Archived summaries

## Usage Example

```python
# Via MCP tools in Claude Code:

# Add a core memory
add_core_memory("tdd-implementer", "Write tests before implementation")

# Track recent work
add_recent_memory("tdd-implementer", "Fixed bug in login validation")
add_recent_memory("tdd-implementer", "Added unit tests for auth module")

# Set current task
set_current_task("tdd-implementer", "Implementing password reset flow")

# Record completed work
add_episodic_memory(
    "tdd-implementer",
    "Completed OAuth integration with Google and GitHub",
    "oauth,authentication"
)

# Get overview
get_memory_summary("tdd-implementer")
```

## Development

### Project Structure
```
agent-memory/
├── src/
│   ├── __init__.py
│   ├── server.py       # Main MCP server
│   ├── database.py     # SQLite operations
│   └── summarizer.py   # LLM-based summarization
├── tests/
├── agent_memory.db     # SQLite database (created on first run)
├── requirements.txt
└── README.md
```

### Running Tests

```bash
cd agent-memory
python -m pytest tests/
```

## Future Enhancements

- Memory importance scoring
- Cross-agent memory sharing
- Memory visualization dashboard
- Semantic search with embeddings
- Configurable summarization thresholds
- Memory export/import for backup

## Sources

Built using:
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)
- [Anthropic Claude API](https://www.anthropic.com/api)
- SQLite for persistence
