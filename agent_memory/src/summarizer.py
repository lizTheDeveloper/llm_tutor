"""Memory summarization using LLM"""

import os
import logging
from typing import List, Dict, Optional
from anthropic import Anthropic

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MemorySummarizer:
    """Handles summarization of recent memories using LLM"""

    def __init__(self, api_key: Optional[str] = None):
        """Initialize summarizer with Anthropic API

        Args:
            api_key: Optional Anthropic API key (defaults to env var)
        """
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable not set")

        self.client = Anthropic(api_key=self.api_key)

    def summarize_recent_memories(self, memories: List[Dict], agent_id: str) -> str:
        """Summarize a list of recent memories into 1-2 sentences

        Args:
            memories: List of memory dicts with 'memory' and 'created_at' keys
            agent_id: Agent identifier for context

        Returns:
            Summary string (1-2 sentences)
        """
        if not memories:
            return "No memories to summarize."

        # Format memories for prompt
        memory_list = "\n".join([
            f"{idx + 1}. {mem['memory']}"
            for idx, mem in enumerate(memories)
        ])

        prompt = f"""You are helping the '{agent_id}' agent distill learnings from recent work.

The agent has recorded these {len(memories)} recent memories:

{memory_list}

Your task is to extract distilled learnings and insights from these memories. Focus on:
1. Patterns and recurring themes
2. Key accomplishments or milestones
3. Important decisions or approaches taken
4. Lessons learned or best practices discovered

Create a concise 2-3 sentence summary that captures the LEARNINGS, not just what happened. Think of this as knowledge the agent should remember going forward.

Return ONLY the distilled learnings, no additional explanation or commentary."""

        try:
            message = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=200,
                messages=[{
                    "role": "user",
                    "content": prompt
                }]
            )

            summary = message.content[0].text.strip()
            logger.info(f"Successfully distilled {len(memories)} memories for {agent_id}")
            return summary

        except Exception as error:
            logger.error(f"Error distilling memories: {error}")
            # Fallback: simple concatenation if API fails
            fallback_summary = f"Learnings from {len(memories)} recent activities: " + "; ".join([
                mem['memory'] for mem in memories[:3]
            ])
            if len(memories) > 3:
                fallback_summary += f" (and {len(memories) - 3} more actions taken)"
            return fallback_summary[:500]  # Limit length
