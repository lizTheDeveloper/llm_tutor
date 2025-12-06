"""Agent Memory MCP Server - Main server implementation"""

import os
import sys
import threading
import logging
from typing import Optional, List
from mcp.server.fastmcp import FastMCP

from .database import MemoryDatabase
from .summarizer import MemorySummarizer

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Initialize FastMCP server
mcp = FastMCP(name="agent-memory")

# Initialize database
db_path = os.path.join(os.path.dirname(__file__), "..", "agent_memory.db")
database = MemoryDatabase(db_path=db_path)

# Initialize summarizer lazily (only when needed)
_summarizer = None

def get_summarizer():
    """Get or create summarizer instance"""
    global _summarizer
    if _summarizer is None:
        _summarizer = MemorySummarizer()
    return _summarizer


def _background_distill_and_archive(agent_id: str, memories: list):
    """Background worker to distill learnings and archive memories

    This runs in a separate thread to avoid blocking the MCP response.

    Args:
        agent_id: Agent identifier
        memories: List of memories to distill
    """
    try:
        logger.info(f"[Background] Starting distillation for {agent_id} ({len(memories)} memories)")

        # Distill learnings from memories
        distilled_learnings = get_summarizer().summarize_recent_memories(memories, agent_id)

        # Store in compost
        database.add_to_compost(agent_id, distilled_learnings, len(memories))

        # Clear recent memories
        database.clear_recent_memories(agent_id)

        logger.info(f"[Background] Completed distillation for {agent_id}")
        logger.info(f"[Background] Distilled learnings: {distilled_learnings}")

    except Exception as error:
        logger.error(f"[Background] Error distilling memories for {agent_id}: {error}")


# Core Memory Tools

@mcp.tool()
def add_core_memory(agent_id: str, memory: str) -> str:
    """Add a permanent core memory (personality principle or key learning)

    Args:
        agent_id: Agent identifier (e.g., 'tdd-implementer', 'project-manager')
        memory: Single sentence describing the core memory

    Returns:
        Confirmation message with memory ID
    """
    try:
        memory_id = database.add_core_memory(agent_id, memory)
        return f"Core memory added for {agent_id} (ID: {memory_id}): {memory}"
    except Exception as error:
        return f"Error adding core memory: {str(error)}"


@mcp.tool()
def get_core_memories(agent_id: str) -> str:
    """Retrieve all core memories for an agent

    Args:
        agent_id: Agent identifier

    Returns:
        Formatted list of core memories
    """
    memories = database.get_core_memories(agent_id)

    if not memories:
        return f"No core memories found for {agent_id}"

    result = f"Core Memories for {agent_id}:\n\n"
    for mem in memories:
        result += f"- {mem['memory']}\n"

    return result


@mcp.tool()
def delete_core_memory(agent_id: str, memory_id: int) -> str:
    """Remove a core memory (use cautiously)

    Args:
        agent_id: Agent identifier
        memory_id: ID of the memory to delete

    Returns:
        Confirmation message
    """
    success = database.delete_core_memory(agent_id, memory_id)
    if success:
        return f"Core memory {memory_id} deleted for {agent_id}"
    else:
        return f"Core memory {memory_id} not found for {agent_id}"


# Recent Memory Tools

@mcp.tool()
def add_recent_memory(agent_id: str, memory: str) -> str:
    """Add to recent memory (auto-summarizes when full at 10 entries)

    Args:
        agent_id: Agent identifier
        memory: Single sentence describing the recent activity

    Returns:
        Confirmation message, warning if summarization triggered
    """
    memory_id, needs_summarization = database.add_recent_memory(agent_id, memory)

    if needs_summarization:
        # Get all memories before clearing
        all_memories = database.get_all_recent_memories_for_summary(agent_id)

        # Launch background thread to distill learnings
        distill_thread = threading.Thread(
            target=_background_distill_and_archive,
            args=(agent_id, all_memories),
            daemon=True,
            name=f"distill-{agent_id}"
        )
        distill_thread.start()

        logger.info(f"Launched background distillation for {agent_id} (thread: {distill_thread.name})")

        return (
            f"Recent memory added (ID: {memory_id}). "
            f"🧠 Memory limit reached! Distilling {len(all_memories)} memories into learnings in background...\n"
            f"Note: Distillation is running asynchronously. Check memory summary in a moment to see the distilled learnings in compost."
        )
    else:
        return f"Recent memory added for {agent_id} (ID: {memory_id}): {memory}"


@mcp.tool()
def get_recent_memories(agent_id: str, limit: int = 10) -> str:
    """Retrieve recent memories (up to 10)

    Args:
        agent_id: Agent identifier
        limit: Maximum number of memories to return (default: 10)

    Returns:
        Formatted list of recent memories
    """
    memories = database.get_recent_memories(agent_id, limit)

    if not memories:
        return f"No recent memories found for {agent_id}"

    result = f"Recent Memories for {agent_id} ({len(memories)} total):\n\n"
    for mem in memories:
        result += f"- [{mem['created_at']}] {mem['memory']}\n"

    return result


@mcp.tool()
def clear_recent_memories(agent_id: str) -> str:
    """Clear recent memories (moves all to compost with summary)

    Args:
        agent_id: Agent identifier

    Returns:
        Confirmation message
    """
    all_memories = database.get_all_recent_memories_for_summary(agent_id)

    if not all_memories:
        return f"No recent memories to clear for {agent_id}"

    # Summarize and move to compost
    summary = get_summarizer().summarize_recent_memories(all_memories, agent_id)
    database.add_to_compost(agent_id, summary, len(all_memories))

    # Clear recent memories
    count = database.clear_recent_memories(agent_id)

    return (
        f"Cleared {count} recent memories for {agent_id}. "
        f"Summarized and moved to compost:\n{summary}"
    )


# Current Task Tools

@mcp.tool()
def set_current_task(agent_id: str, task: str) -> str:
    """Set or update the agent's current task

    Args:
        agent_id: Agent identifier
        task: Single sentence describing the current task

    Returns:
        Confirmation message, previous task moved to episodic memory
    """
    previous_task, task_id = database.set_current_task(agent_id, task)

    result = f"Current task set for {agent_id}: {task}"

    if previous_task:
        # Move previous task to episodic memory
        database.add_episodic_memory(
            agent_id,
            f"Completed task: {previous_task}",
            tags="task,completed"
        )
        result += f"\n\nPrevious task moved to episodic memory: {previous_task}"

    return result


@mcp.tool()
def get_current_task(agent_id: str) -> str:
    """Get the agent's current task

    Args:
        agent_id: Agent identifier

    Returns:
        Current task or message if none set
    """
    task_info = database.get_current_task(agent_id)

    if not task_info:
        return f"No current task set for {agent_id}"

    return (
        f"Current Task for {agent_id}:\n\n"
        f"{task_info['task']}\n\n"
        f"Started: {task_info['started_at']}\n"
        f"Updated: {task_info['updated_at']}"
    )


# Episodic Memory Tools

@mcp.tool()
def add_episodic_memory(agent_id: str, memory: str, tags: Optional[str] = None) -> str:
    """Record a completed task or significant event

    Args:
        agent_id: Agent identifier
        memory: Single sentence describing the episode
        tags: Optional comma-separated tags (e.g., 'bug-fix,frontend')

    Returns:
        Confirmation message with memory ID
    """
    memory_id = database.add_episodic_memory(agent_id, memory, tags)
    tag_info = f" (tags: {tags})" if tags else ""
    return f"Episodic memory added for {agent_id} (ID: {memory_id}){tag_info}: {memory}"


@mcp.tool()
def search_episodic_memories(
    agent_id: str,
    keywords: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    limit: int = 50
) -> str:
    """Search episodic memories by keywords or date range

    Args:
        agent_id: Agent identifier
        keywords: Optional search keywords
        from_date: Optional start date (ISO format: YYYY-MM-DD)
        to_date: Optional end date (ISO format: YYYY-MM-DD)
        limit: Maximum results (default: 50)

    Returns:
        Formatted list of matching memories
    """
    memories = database.search_episodic_memories(
        agent_id, keywords, from_date, to_date, limit
    )

    if not memories:
        search_criteria = []
        if keywords:
            search_criteria.append(f"keywords: {keywords}")
        if from_date:
            search_criteria.append(f"from: {from_date}")
        if to_date:
            search_criteria.append(f"to: {to_date}")

        criteria_str = ", ".join(search_criteria) if search_criteria else "all"
        return f"No episodic memories found for {agent_id} ({criteria_str})"

    result = f"Episodic Memories for {agent_id} ({len(memories)} results):\n\n"
    for mem in memories:
        tag_info = f" [{mem['tags']}]" if mem['tags'] else ""
        result += f"- [{mem['created_at']}]{tag_info} {mem['memory']}\n"

    return result


# Summary Tools

@mcp.tool()
def get_memory_summary(agent_id: str) -> str:
    """Get a complete overview of agent's memory state

    Args:
        agent_id: Agent identifier

    Returns:
        Summary including counts and recent entries from all layers
    """
    summary = database.get_memory_summary(agent_id)

    result = f"Memory Summary for {agent_id}:\n\n"
    result += f"Core Memories: {summary['core_memories_count']}\n"
    result += f"Recent Memories: {summary['recent_memories_count']}/10\n"
    result += f"Current Task: {summary['current_task'] or 'None'}\n"
    result += f"Episodic Memories: {summary['episodic_memories_count']}\n"
    result += f"Memory Compost: {summary['memory_compost_count']} summaries\n"

    # Add samples
    result += "\n---\n\n"

    core_memories = database.get_core_memories(agent_id)
    if core_memories:
        result += "Core Memories:\n"
        for mem in core_memories[:3]:
            result += f"- {mem['memory']}\n"
        if len(core_memories) > 3:
            result += f"... and {len(core_memories) - 3} more\n"
        result += "\n"

    recent_memories = database.get_recent_memories(agent_id, 3)
    if recent_memories:
        result += "Recent Memories (last 3):\n"
        for mem in recent_memories:
            result += f"- {mem['memory']}\n"
        result += "\n"

    compost = database.get_compost_memories(agent_id, 2)
    if compost:
        result += "Recent Compost Summaries:\n"
        for entry in compost:
            result += f"- [{entry['archived_at']}] {entry['summary']} ({entry['original_count']} memories)\n"

    return result


# Run the server
if __name__ == "__main__":
    mcp.run()
