"""Database operations for agent memory system"""

import sqlite3
import os
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from contextlib import contextmanager


class MemoryDatabase:
    """Manages SQLite database for agent memories"""

    def __init__(self, db_path: str = "agent_memory.db"):
        """Initialize database connection

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self.initialize_database()

    @contextmanager
    def get_connection(self):
        """Context manager for database connections"""
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        except Exception as error:
            connection.rollback()
            raise error
        finally:
            connection.close()

    def initialize_database(self):
        """Create database schema if not exists"""
        with self.get_connection() as connection:
            cursor = connection.cursor()

            # Core memories table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS core_memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    agent_id TEXT NOT NULL,
                    memory TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(agent_id, memory)
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_core_agent ON core_memories(agent_id)")

            # Recent memories table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS recent_memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    agent_id TEXT NOT NULL,
                    memory TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_recent_agent ON recent_memories(agent_id)")

            # Current task table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS current_task (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    agent_id TEXT NOT NULL UNIQUE,
                    task TEXT NOT NULL,
                    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Episodic memories table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS episodic_memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    agent_id TEXT NOT NULL,
                    memory TEXT NOT NULL,
                    tags TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_episodic_agent ON episodic_memories(agent_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_episodic_created ON episodic_memories(created_at)")

            # Memory compost table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS memory_compost (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    agent_id TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    original_count INTEGER DEFAULT 0,
                    archived_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_compost_agent ON memory_compost(agent_id)")

    # Core Memory Operations

    def add_core_memory(self, agent_id: str, memory: str) -> int:
        """Add a core memory for an agent

        Args:
            agent_id: Agent identifier
            memory: Single sentence memory

        Returns:
            Memory ID
        """
        with self.get_connection() as connection:
            cursor = connection.cursor()
            cursor.execute(
                "INSERT INTO core_memories (agent_id, memory) VALUES (?, ?)",
                (agent_id, memory)
            )
            return cursor.lastrowid

    def get_core_memories(self, agent_id: str) -> List[Dict]:
        """Get all core memories for an agent

        Args:
            agent_id: Agent identifier

        Returns:
            List of core memories
        """
        with self.get_connection() as connection:
            cursor = connection.cursor()
            cursor.execute(
                "SELECT id, memory, created_at FROM core_memories WHERE agent_id = ? ORDER BY created_at ASC",
                (agent_id,)
            )
            return [dict(row) for row in cursor.fetchall()]

    def delete_core_memory(self, agent_id: str, memory_id: int) -> bool:
        """Delete a core memory

        Args:
            agent_id: Agent identifier
            memory_id: Memory ID to delete

        Returns:
            True if deleted, False if not found
        """
        with self.get_connection() as connection:
            cursor = connection.cursor()
            cursor.execute(
                "DELETE FROM core_memories WHERE id = ? AND agent_id = ?",
                (memory_id, agent_id)
            )
            return cursor.rowcount > 0

    # Recent Memory Operations

    def add_recent_memory(self, agent_id: str, memory: str) -> Tuple[int, bool]:
        """Add a recent memory, return if summarization needed

        Args:
            agent_id: Agent identifier
            memory: Single sentence memory

        Returns:
            Tuple of (memory_id, needs_summarization)
        """
        with self.get_connection() as connection:
            cursor = connection.cursor()
            cursor.execute(
                "INSERT INTO recent_memories (agent_id, memory) VALUES (?, ?)",
                (agent_id, memory)
            )
            memory_id = cursor.lastrowid

            # Check count
            cursor.execute(
                "SELECT COUNT(*) as count FROM recent_memories WHERE agent_id = ?",
                (agent_id,)
            )
            count = cursor.fetchone()['count']

            return memory_id, count >= 10

    def get_recent_memories(self, agent_id: str, limit: int = 10) -> List[Dict]:
        """Get recent memories for an agent

        Args:
            agent_id: Agent identifier
            limit: Maximum number of memories to return

        Returns:
            List of recent memories
        """
        with self.get_connection() as connection:
            cursor = connection.cursor()
            cursor.execute(
                "SELECT id, memory, created_at FROM recent_memories WHERE agent_id = ? ORDER BY created_at DESC LIMIT ?",
                (agent_id, limit)
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_all_recent_memories_for_summary(self, agent_id: str) -> List[Dict]:
        """Get all recent memories for summarization

        Args:
            agent_id: Agent identifier

        Returns:
            List of all recent memories
        """
        with self.get_connection() as connection:
            cursor = connection.cursor()
            cursor.execute(
                "SELECT id, memory, created_at FROM recent_memories WHERE agent_id = ? ORDER BY created_at ASC",
                (agent_id,)
            )
            return [dict(row) for row in cursor.fetchall()]

    def clear_recent_memories(self, agent_id: str) -> int:
        """Clear all recent memories for an agent

        Args:
            agent_id: Agent identifier

        Returns:
            Number of memories cleared
        """
        with self.get_connection() as connection:
            cursor = connection.cursor()
            cursor.execute(
                "DELETE FROM recent_memories WHERE agent_id = ?",
                (agent_id,)
            )
            return cursor.rowcount

    # Current Task Operations

    def set_current_task(self, agent_id: str, task: str) -> Tuple[Optional[str], int]:
        """Set current task, return previous task

        Args:
            agent_id: Agent identifier
            task: Current task description

        Returns:
            Tuple of (previous_task, task_id)
        """
        with self.get_connection() as connection:
            cursor = connection.cursor()

            # Get previous task
            cursor.execute(
                "SELECT task FROM current_task WHERE agent_id = ?",
                (agent_id,)
            )
            result = cursor.fetchone()
            previous_task = result['task'] if result else None

            # Update or insert
            cursor.execute("""
                INSERT INTO current_task (agent_id, task, started_at, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                ON CONFLICT(agent_id) DO UPDATE SET
                    task = excluded.task,
                    updated_at = CURRENT_TIMESTAMP
            """, (agent_id, task))

            return previous_task, cursor.lastrowid

    def get_current_task(self, agent_id: str) -> Optional[Dict]:
        """Get current task for an agent

        Args:
            agent_id: Agent identifier

        Returns:
            Current task dict or None
        """
        with self.get_connection() as connection:
            cursor = connection.cursor()
            cursor.execute(
                "SELECT id, task, started_at, updated_at FROM current_task WHERE agent_id = ?",
                (agent_id,)
            )
            result = cursor.fetchone()
            return dict(result) if result else None

    # Episodic Memory Operations

    def add_episodic_memory(self, agent_id: str, memory: str, tags: Optional[str] = None) -> int:
        """Add an episodic memory

        Args:
            agent_id: Agent identifier
            memory: Single sentence memory
            tags: Optional comma-separated tags

        Returns:
            Memory ID
        """
        with self.get_connection() as connection:
            cursor = connection.cursor()
            cursor.execute(
                "INSERT INTO episodic_memories (agent_id, memory, tags) VALUES (?, ?, ?)",
                (agent_id, memory, tags)
            )
            return cursor.lastrowid

    def search_episodic_memories(
        self,
        agent_id: str,
        keywords: Optional[str] = None,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict]:
        """Search episodic memories

        Args:
            agent_id: Agent identifier
            keywords: Optional search keywords
            from_date: Optional start date (ISO format)
            to_date: Optional end date (ISO format)
            limit: Maximum results

        Returns:
            List of matching memories
        """
        with self.get_connection() as connection:
            cursor = connection.cursor()

            query = "SELECT id, memory, tags, created_at FROM episodic_memories WHERE agent_id = ?"
            params = [agent_id]

            if keywords:
                query += " AND (memory LIKE ? OR tags LIKE ?)"
                search_term = f"%{keywords}%"
                params.extend([search_term, search_term])

            if from_date:
                query += " AND created_at >= ?"
                params.append(from_date)

            if to_date:
                query += " AND created_at <= ?"
                params.append(to_date)

            query += " ORDER BY created_at DESC LIMIT ?"
            params.append(limit)

            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    # Memory Compost Operations

    def add_to_compost(self, agent_id: str, summary: str, original_count: int) -> int:
        """Add summarized memories to compost

        Args:
            agent_id: Agent identifier
            summary: Summary of memories
            original_count: Number of original memories summarized

        Returns:
            Compost entry ID
        """
        with self.get_connection() as connection:
            cursor = connection.cursor()
            cursor.execute(
                "INSERT INTO memory_compost (agent_id, summary, original_count) VALUES (?, ?, ?)",
                (agent_id, summary, original_count)
            )
            return cursor.lastrowid

    def get_compost_memories(self, agent_id: str, limit: int = 20) -> List[Dict]:
        """Get compost memories for an agent

        Args:
            agent_id: Agent identifier
            limit: Maximum number of entries

        Returns:
            List of compost entries
        """
        with self.get_connection() as connection:
            cursor = connection.cursor()
            cursor.execute(
                "SELECT id, summary, original_count, archived_at FROM memory_compost WHERE agent_id = ? ORDER BY archived_at DESC LIMIT ?",
                (agent_id, limit)
            )
            return [dict(row) for row in cursor.fetchall()]

    # Summary Operations

    def get_memory_summary(self, agent_id: str) -> Dict:
        """Get summary of all memory layers for an agent

        Args:
            agent_id: Agent identifier

        Returns:
            Dict with counts and sample entries
        """
        with self.get_connection() as connection:
            cursor = connection.cursor()

            # Core memories count
            cursor.execute("SELECT COUNT(*) as count FROM core_memories WHERE agent_id = ?", (agent_id,))
            core_count = cursor.fetchone()['count']

            # Recent memories count
            cursor.execute("SELECT COUNT(*) as count FROM recent_memories WHERE agent_id = ?", (agent_id,))
            recent_count = cursor.fetchone()['count']

            # Current task
            cursor.execute("SELECT task FROM current_task WHERE agent_id = ?", (agent_id,))
            result = cursor.fetchone()
            current_task = result['task'] if result else None

            # Episodic memories count
            cursor.execute("SELECT COUNT(*) as count FROM episodic_memories WHERE agent_id = ?", (agent_id,))
            episodic_count = cursor.fetchone()['count']

            # Compost count
            cursor.execute("SELECT COUNT(*) as count FROM memory_compost WHERE agent_id = ?", (agent_id,))
            compost_count = cursor.fetchone()['count']

            return {
                'agent_id': agent_id,
                'core_memories_count': core_count,
                'recent_memories_count': recent_count,
                'current_task': current_task,
                'episodic_memories_count': episodic_count,
                'memory_compost_count': compost_count
            }
