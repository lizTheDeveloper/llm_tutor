"""Basic tests for agent memory system"""

import os
import sys

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src'))

from database import MemoryDatabase


def test_database_initialization():
    """Test database initialization"""
    print("Testing database initialization...")

    # Create test database
    test_db_path = "test_memory.db"
    if os.path.exists(test_db_path):
        os.remove(test_db_path)

    database = MemoryDatabase(db_path=test_db_path)
    print("✓ Database created successfully")

    # Test core memory
    print("\nTesting core memory...")
    memory_id = database.add_core_memory("test-agent", "Always write tests first")
    print(f"✓ Added core memory with ID: {memory_id}")

    memories = database.get_core_memories("test-agent")
    assert len(memories) == 1
    assert memories[0]['memory'] == "Always write tests first"
    print(f"✓ Retrieved core memory: {memories[0]['memory']}")

    # Test recent memory
    print("\nTesting recent memory...")
    for index in range(5):
        memory_id, needs_summary = database.add_recent_memory(
            "test-agent",
            f"Recent memory {index + 1}"
        )
        print(f"✓ Added recent memory {index + 1} (ID: {memory_id}, needs_summary: {needs_summary})")

    recent = database.get_recent_memories("test-agent")
    assert len(recent) == 5
    print(f"✓ Retrieved {len(recent)} recent memories")

    # Test current task
    print("\nTesting current task...")
    previous, task_id = database.set_current_task("test-agent", "Testing the memory system")
    print(f"✓ Set current task (ID: {task_id}, previous: {previous})")

    task_info = database.get_current_task("test-agent")
    assert task_info['task'] == "Testing the memory system"
    print(f"✓ Retrieved current task: {task_info['task']}")

    # Test episodic memory
    print("\nTesting episodic memory...")
    episode_id = database.add_episodic_memory(
        "test-agent",
        "Completed test suite implementation",
        "testing,completed"
    )
    print(f"✓ Added episodic memory (ID: {episode_id})")

    episodes = database.search_episodic_memories("test-agent")
    assert len(episodes) == 1
    print(f"✓ Retrieved {len(episodes)} episodic memories")

    # Test memory summary
    print("\nTesting memory summary...")
    summary = database.get_memory_summary("test-agent")
    print(f"✓ Memory summary:")
    print(f"  - Core memories: {summary['core_memories_count']}")
    print(f"  - Recent memories: {summary['recent_memories_count']}")
    print(f"  - Current task: {summary['current_task']}")
    print(f"  - Episodic memories: {summary['episodic_memories_count']}")
    print(f"  - Compost entries: {summary['memory_compost_count']}")

    # Test auto-summarization threshold
    print("\nTesting auto-summarization threshold...")
    for index in range(5, 10):
        memory_id, needs_summary = database.add_recent_memory(
            "test-agent",
            f"Recent memory {index + 1}"
        )
        if needs_summary:
            print(f"✓ Summarization triggered at {index + 1} memories")
            break

    # Cleanup
    os.remove(test_db_path)
    print("\n✓ All tests passed!")


if __name__ == "__main__":
    test_database_initialization()
