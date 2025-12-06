#!/usr/bin/env python3
"""
Matrix Communications Agent for LLM Tutor Platform

Reports deployment milestones to #agentic-sdlc:themultiverse.school (max once/day)
Listens for user feedback and creates issues/notes with prompt defenses
"""
import asyncio
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from nio import (
    AsyncClient,
    LoginResponse,
    MatrixRoom,
    RoomMessageText,
    JoinError,
)

# Configuration
HOMESERVER = "https://matrix.themultiverse.school"
REGISTRATION_TOKEN = "multiversemultiswarm"
BOT_USERNAME = "llm-tutor-agent"
BOT_PASSWORD = os.getenv("MATRIX_BOT_PASSWORD", "change-me-in-production")
CHANNEL_ROOM_ID = "#agentic-sdlc:themultiverse.school"

# Deployment info
DEPLOYMENT_URL = "http://34.88.245.170"
PROJECT_ROOT = Path(__file__).parent.parent


class DeploymentReporter:
    """Handles deployment milestone reporting with rate limiting."""

    def __init__(self, state_file: Path):
        self.state_file = state_file
        self.state = self._load_state()

    def _load_state(self) -> dict:
        """Load last report timestamp from state file."""
        if self.state_file.exists():
            with open(self.state_file, 'r') as f:
                return json.load(f)
        return {"last_report": None, "last_commit": None}

    def _save_state(self):
        """Save state to file."""
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.state_file, 'w') as f:
            json.dump(self.state, f, indent=2)

    def should_report(self, current_commit: str) -> bool:
        """Check if we should report (max once per day, or if new commit)."""
        # Always report on new commits
        if self.state["last_commit"] != current_commit:
            return True

        # Rate limit: max once per day
        if self.state["last_report"] is None:
            return True

        last_report = datetime.fromisoformat(self.state["last_report"])
        if datetime.now() - last_report > timedelta(days=1):
            return True

        return False

    def mark_reported(self, commit: str):
        """Mark that we've reported this deployment."""
        self.state["last_report"] = datetime.now().isoformat()
        self.state["last_commit"] = commit
        self._save_state()


class FeedbackValidator:
    """Validates user feedback with prompt defenses."""

    DANGEROUS_KEYWORDS = [
        "delete", "drop", "remove", "destroy", "shutdown",
        "stop", "kill", "terminate", "reset", "wipe",
        "rm -rf", "sudo", "exec", "eval", "system"
    ]

    COMMAND_PATTERNS = [
        "run ", "execute ", "shell ", "bash ", "sh ",
        "deploy --force", "git push --force", "admin ",
    ]

    @classmethod
    def is_safe(cls, message: str) -> tuple[bool, Optional[str]]:
        """
        Validate user message for safety.

        Returns:
            (is_safe, reason_if_unsafe)
        """
        message_lower = message.lower()

        # Check for dangerous keywords
        for keyword in cls.DANGEROUS_KEYWORDS:
            if keyword in message_lower:
                return False, f"Rejected: contains dangerous keyword '{keyword}'"

        # Check for command injection patterns
        for pattern in cls.COMMAND_PATTERNS:
            if pattern in message_lower:
                return False, f"Rejected: looks like command injection '{pattern}'"

        # Check message length (prevent DoS)
        if len(message) > 2000:
            return False, "Rejected: message too long (max 2000 chars)"

        return True, None


class LLMTutorMatrixAgent:
    """Matrix agent for LLM Tutor milestone reporting and feedback."""

    def __init__(self):
        self.client = AsyncClient(HOMESERVER, f"@{BOT_USERNAME}:themultiverse.school")
        self.reporter = DeploymentReporter(PROJECT_ROOT / ".matrix-state.json")
        self.feedback_file = PROJECT_ROOT / "feedback" / "matrix-feedback.jsonl"

    async def login(self):
        """Login to Matrix account."""
        try:
            response = await self.client.login(BOT_PASSWORD)

            if isinstance(response, LoginResponse):
                print(f"✅ Logged in as {self.client.user}")
                return True
            else:
                print(f"❌ Login failed: {response}")
                print(f"\n⚠️  Please register the bot account manually first:")
                print(f"   1. Go to https://app.element.io")
                print(f"   2. Register account: @{BOT_USERNAME}:themultiverse.school")
                print(f"   3. Use registration token: {REGISTRATION_TOKEN}")
                print(f"   4. Set password to: {BOT_PASSWORD}")
                return False
        except Exception as e:
            print(f"❌ Login error: {e}")
            return False

    async def join_channel(self):
        """Join the agentic-sdlc channel."""
        response = await self.client.join(CHANNEL_ROOM_ID)
        if isinstance(response, JoinError):
            print(f"❌ Failed to join {CHANNEL_ROOM_ID}: {response.message}")
            return False
        print(f"✅ Joined channel: {CHANNEL_ROOM_ID}")
        return True

    def get_recent_changes(self, limit: int = 5) -> list[str]:
        """Get recent git commits."""
        import subprocess
        try:
            result = subprocess.run(
                ["git", "log", f"-{limit}", "--oneline"],
                cwd=PROJECT_ROOT,
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.stdout.strip().split("\n")
        except Exception as e:
            print(f"Warning: Could not fetch git log: {e}")
            return ["Unable to fetch commit history"]

    def get_current_commit(self) -> str:
        """Get current git commit hash."""
        import subprocess
        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=PROJECT_ROOT,
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.stdout.strip()[:8]
        except Exception:
            return "unknown"

    async def report_deployment(self):
        """Report deployment milestone to channel (if due)."""
        current_commit = self.get_current_commit()

        if not self.reporter.should_report(current_commit):
            print("⏭️  Skipping report (already reported within 24h)")
            return

        recent_changes = self.get_recent_changes(5)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M UTC")

        message = f"""🚀 **LLM Tutor Platform Deployment**

📅 Deployed: {timestamp}
🔖 Commit: {current_commit}
🌍 Location: {DEPLOYMENT_URL}

**Recent Changes:**
{chr(10).join(f"• {change}" for change in recent_changes)}

**Endpoints:**
• Frontend: {DEPLOYMENT_URL}/
• API: {DEPLOYMENT_URL}/api/
• Health: {DEPLOYMENT_URL}/health

Test the platform and send feedback to this channel!
"""

        await self.client.room_send(
            room_id=CHANNEL_ROOM_ID,
            message_type="m.room.message",
            content={
                "msgtype": "m.text",
                "body": message,
                "format": "org.matrix.custom.html",
                "formatted_body": message.replace("**", "<b>").replace("**", "</b>")
            }
        )

        self.reporter.mark_reported(current_commit)
        print(f"✅ Deployment report sent to {CHANNEL_ROOM_ID}")

    def save_feedback(self, sender: str, message: str, is_safe: bool, reason: Optional[str]):
        """Save user feedback to JSONL file for later processing."""
        self.feedback_file.parent.mkdir(parents=True, exist_ok=True)

        feedback_entry = {
            "timestamp": datetime.now().isoformat(),
            "sender": sender,
            "message": message,
            "is_safe": is_safe,
            "rejection_reason": reason,
            "processed": False
        }

        with open(self.feedback_file, 'a') as f:
            f.write(json.dumps(feedback_entry) + "\n")

    async def handle_message(self, room: MatrixRoom, event: RoomMessageText):
        """Handle incoming messages with security validation."""
        # Ignore our own messages
        if event.sender == self.client.user:
            return

        # Only respond in the agentic-sdlc channel
        if room.room_id != CHANNEL_ROOM_ID:
            return

        message_body = event.body.strip()

        # Validate message safety
        is_safe, reason = FeedbackValidator.is_safe(message_body)

        # Save all feedback (safe or not) for review
        self.save_feedback(event.sender, message_body, is_safe, reason)

        if not is_safe:
            # Respond to dangerous messages
            await self.client.room_send(
                room_id=room.room_id,
                message_type="m.room.message",
                content={
                    "msgtype": "m.text",
                    "body": f"⚠️ {reason}\n\nPlease rephrase your feedback constructively."
                }
            )
            print(f"🛡️  Blocked unsafe message from {event.sender}: {reason}")
        else:
            # Acknowledge safe feedback
            await self.client.room_send(
                room_id=room.room_id,
                message_type="m.room.message",
                content={
                    "msgtype": "m.text",
                    "body": f"✅ Feedback received from {event.sender}. This will be reviewed and may result in an issue being created."
                }
            )
            print(f"📝 Feedback saved from {event.sender}")

    async def start_listener(self):
        """Start listening for messages."""
        self.client.add_event_callback(self.handle_message, RoomMessageText)
        print(f"👂 Listening for messages in {CHANNEL_ROOM_ID}")
        await self.client.sync_forever(timeout=30000)

    async def run(self, mode: str = "report"):
        """
        Run the agent in specified mode.

        Args:
            mode: "report" for one-time deployment report, "listen" for continuous feedback
        """
        try:
            if not await self.login():
                return

            if not await self.join_channel():
                return

            if mode == "report":
                await self.report_deployment()
            elif mode == "listen":
                await self.start_listener()
            else:
                print(f"❌ Unknown mode: {mode}")

        finally:
            await self.client.close()


async def main():
    """Main entry point."""
    mode = sys.argv[1] if len(sys.argv) > 1 else "report"
    agent = LLMTutorMatrixAgent()
    await agent.run(mode)


if __name__ == "__main__":
    asyncio.run(main())
