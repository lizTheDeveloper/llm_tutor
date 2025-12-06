# Agent Memory System Requirements

## Overview

An MCP (Model Context Protocol) server that provides persistent memory capabilities for AI agents working on the LLM Tutor project. The system enables agents to maintain context across sessions through multiple memory layers inspired by human memory systems and the "Inside Out" movie concept of core memories.

## Memory Architecture

### 1. Core Memories
- **Purpose**: Fundamental personality principles and project-wide learnings that define the agent's identity
- **Characteristics**:
  - Never archived or deleted
  - Represents the agent's "personality" and "values"
  - Examples: "Always use raw SQL over SQLAlchemy for queries", "Prefer integration tests over mocked unit tests"
- **Storage**: Permanent, no automatic modification
- **Analogy**: Like core memories in "Inside Out" - fundamental beliefs that shape all actions

### 2. Recent Memory
- **Purpose**: Short-term working memory of recent activities
- **Characteristics**:
  - Limited to 10 entries maximum
  - Each entry is a single sentence
  - When capacity reached (10 entries), automatically summarize and move to Memory Compost
  - FIFO (First In, First Out) with summarization
- **Storage**: Active table, auto-summarized

### 3. Current Task
- **Purpose**: What the agent is actively working on right now
- **Characteristics**:
  - Single entry (current focus)
  - Updates frequently as agent switches tasks
  - Historical current tasks move to Episodic Memory
- **Storage**: Single record per agent, overwritten with history tracking

### 4. Episodic Memory
- **Purpose**: Memories of specific tasks, events, and accomplishments
- **Characteristics**:
  - Long-term storage of completed work
  - Searchable by keywords, dates, agent
  - Each entry is a single sentence describing the episode
- **Storage**: Append-only historical log

### 5. Memory Compost
- **Purpose**: Archive of summarized memories that are no longer actively accessed
- **Characteristics**:
  - Receives summarized batches from Recent Memory
  - Lower priority for retrieval
  - Can be searched if needed
  - Eventual cleanup/compression possible
- **Storage**: Archive table with compression options

## Agents

The system supports four primary agents:
1. `tdd-implementer` - Test-Driven Development implementer
2. `project-manager` - Project planning and coordination
3. `value-chain-expert` - Business value and prioritization
4. `product-requirements` - Requirements gathering and documentation

Each agent has isolated memory spaces within each layer.

## MCP Tools

### Memory Write Operations

1. **add_core_memory**
   - Add a permanent core memory (personality principle or key learning)
   - Parameters: `agent_id`, `memory` (single sentence)
   - Returns: Confirmation with memory ID

2. **add_recent_memory**
   - Add to recent memory (auto-summarizes when full)
   - Parameters: `agent_id`, `memory` (single sentence)
   - Returns: Confirmation, warning if summarization triggered

3. **set_current_task**
   - Set or update the agent's current task
   - Parameters: `agent_id`, `task` (single sentence)
   - Returns: Confirmation, previous task moved to episodic memory

4. **add_episodic_memory**
   - Record a completed task or significant event
   - Parameters: `agent_id`, `memory` (single sentence), optional `tags`
   - Returns: Confirmation with memory ID

### Memory Read Operations

5. **get_core_memories**
   - Retrieve all core memories for an agent
   - Parameters: `agent_id`
   - Returns: List of core memories

6. **get_recent_memories**
   - Retrieve recent memories (up to 10)
   - Parameters: `agent_id`, optional `limit` (default 10)
   - Returns: List of recent memories with timestamps

7. **get_current_task**
   - Get the agent's current task
   - Parameters: `agent_id`
   - Returns: Current task or null if none set

8. **search_episodic_memories**
   - Search episodic memories by keywords or date range
   - Parameters: `agent_id`, optional `keywords`, optional `from_date`, optional `to_date`, optional `limit`
   - Returns: List of matching episodic memories

9. **get_memory_summary**
   - Get a complete overview of agent's memory state
   - Parameters: `agent_id`
   - Returns: Summary including counts and recent entries from all layers

### Memory Management Operations

10. **delete_core_memory**
    - Remove a core memory (use cautiously)
    - Parameters: `agent_id`, `memory_id`
    - Returns: Confirmation

11. **clear_recent_memories**
    - Clear recent memories (moves all to compost)
    - Parameters: `agent_id`
    - Returns: Confirmation

## Auto-Summarization Logic

When Recent Memory reaches 10 entries:
1. Collect all 10 memories
2. Use LLM to generate a 1-2 sentence summary
3. Store summary in Memory Compost with timestamp
4. Clear Recent Memory
5. Log the summarization event

## Database Schema

### SQLite Database: `agent_memory.db`

#### Table: `core_memories`
```sql
CREATE TABLE core_memories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id TEXT NOT NULL,
    memory TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(agent_id, memory)
);
CREATE INDEX idx_core_agent ON core_memories(agent_id);
```

#### Table: `recent_memories`
```sql
CREATE TABLE recent_memories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id TEXT NOT NULL,
    memory TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_recent_agent ON recent_memories(agent_id);
```

#### Table: `current_task`
```sql
CREATE TABLE current_task (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id TEXT NOT NULL UNIQUE,
    task TEXT NOT NULL,
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### Table: `episodic_memories`
```sql
CREATE TABLE episodic_memories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id TEXT NOT NULL,
    memory TEXT NOT NULL,
    tags TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_episodic_agent ON episodic_memories(agent_id);
CREATE INDEX idx_episodic_created ON episodic_memories(created_at);
```

#### Table: `memory_compost`
```sql
CREATE TABLE memory_compost (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id TEXT NOT NULL,
    summary TEXT NOT NULL,
    original_count INTEGER DEFAULT 0,
    archived_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_compost_agent ON memory_compost(agent_id);
```

## Implementation Details

### Technology Stack
- **Language**: Python 3.10+
- **MCP SDK**: `mcp` (FastMCP framework)
- **Database**: SQLite3
- **LLM for Summarization**: Integration with existing backend LLM service or Anthropic API

### File Structure
```
agent-memory/
├── src/
│   ├── __init__.py
│   ├── server.py          # Main MCP server
│   ├── database.py        # Database operations
│   ├── summarizer.py      # Auto-summarization logic
│   └── models.py          # Data models
├── tests/
│   ├── test_server.py
│   ├── test_database.py
│   └── test_summarizer.py
├── agent_memory.db        # SQLite database (gitignored)
├── requirements.txt
└── README.md
```

### Configuration
Add to `.claude/mcp.json`:
```json
{
  "mcpServers": {
    "agent-memory": {
      "command": "python",
      "args": [
        "-m", "agent-memory.src.server"
      ],
      "cwd": "/Users/annhoward/src/llm_tutor",
      "env": {
        "PYTHONPATH": "/Users/annhoward/src/llm_tutor",
        "ANTHROPIC_API_KEY": "${ANTHROPIC_API_KEY}"
      }
    }
  }
}
```

## Success Criteria

1. Agents can store and retrieve memories across all 5 layers
2. Recent memory auto-summarizes at 10 entries
3. Core memories remain permanent and easily accessible
4. Current task tracking works seamlessly
5. Episodic memories are searchable
6. Memory system persists across agent sessions
7. Multiple agents can use the system independently

## Future Enhancements

- Memory importance scoring
- Cross-agent memory sharing for collaboration
- Memory visualization dashboard
- Advanced search with semantic similarity
- Memory export/import for backup
- Configurable summarization thresholds
