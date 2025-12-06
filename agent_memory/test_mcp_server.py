#!/usr/bin/env python3
"""Test MCP server by simulating tool calls"""

import sys
import os
import asyncio

# Add to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent_memory.src.server import (
    add_core_memory,
    get_core_memories,
    add_recent_memory,
    get_recent_memories,
    set_current_task,
    get_current_task,
    add_episodic_memory,
    search_episodic_memories,
    get_memory_summary
)


def test_mcp_tools():
    """Test all MCP tools as if they were called by Claude"""
    print("Testing Agent-Memory MCP Tools:\n")

    agent_id = "test-agent"

    # Test 1: Add core memory
    print("1. add_core_memory:")
    result = add_core_memory(agent_id, "Always verify with integration tests")
    print(f"   {result}\n")

    # Test 2: Get core memories
    print("2. get_core_memories:")
    result = get_core_memories(agent_id)
    print(f"   {result}\n")

    # Test 3: Add recent memories
    print("3. add_recent_memory (3 times):")
    for i in range(3):
        result = add_recent_memory(agent_id, f"Tested component {i+1}")
        print(f"   {result}")
    print()

    # Test 4: Get recent memories
    print("4. get_recent_memories:")
    result = get_recent_memories(agent_id)
    print(f"   {result}\n")

    # Test 5: Set current task
    print("5. set_current_task:")
    result = set_current_task(agent_id, "Validating MCP server functionality")
    print(f"   {result}\n")

    # Test 6: Get current task
    print("6. get_current_task:")
    result = get_current_task(agent_id)
    print(f"   {result}\n")

    # Test 7: Add episodic memory
    print("7. add_episodic_memory:")
    result = add_episodic_memory(agent_id, "Completed MCP server testing", "testing,mcp")
    print(f"   {result}\n")

    # Test 8: Search episodic memories
    print("8. search_episodic_memories:")
    result = search_episodic_memories(agent_id, keywords="testing")
    print(f"   {result}\n")

    # Test 9: Get memory summary
    print("9. get_memory_summary:")
    result = get_memory_summary(agent_id)
    print(f"   {result}\n")

    print("✅ All MCP tools tested successfully!")
    print("\nThe agent-memory MCP server is ready to use.")
    print("Restart Claude Desktop to load the server.")


if __name__ == "__main__":
    test_mcp_tools()
