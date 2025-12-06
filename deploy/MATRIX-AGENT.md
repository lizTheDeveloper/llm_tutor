# Matrix Communications Agent

Autonomous agent that reports deployment milestones and handles user feedback via Matrix protocol.

## Features

### 🚀 Deployment Reporting
- Reports to `#agentic-sdlc:themultiverse.school` after each deployment
- Rate-limited to max once per day (unless new commit)
- Shows deployment URL, commit hash, and recent changes

### 📝 User Feedback Listener
- Continuously listens for user messages in the channel
- Validates messages with prompt defenses (blocks malicious commands)
- Saves feedback to `feedback/matrix-feedback.jsonl` for review
- Can be processed by autonomous agents to create issues

### 🛡️ Security Features

**Prompt Defenses:**
- Blocks dangerous keywords (delete, drop, sudo, exec, etc.)
- Prevents command injection patterns
- Rate limits message length (max 2000 chars)
- Logs all attempts for security review

**Rejected Examples:**
- "delete the deployment" ❌
- "run sudo rm -rf /" ❌
- "deploy --force to production" ❌
- "execute shell command..." ❌

**Accepted Examples:**
- "The login page has a typo in the header" ✅
- "Feature request: add dark mode" ✅
- "Bug: API returns 500 on /exercises endpoint" ✅

## Setup

### On the VM

```bash
# Set bot password (replace with secure password)
export MATRIX_BOT_PASSWORD="your-secure-password-here"

# Run setup script
./deploy/setup-matrix-agent.sh
```

This will:
1. Install matrix-nio in the venv
2. Create systemd service for continuous feedback listening
3. Add deployment reporting to deploy.sh
4. Start the listener service

### Manual Testing

```bash
# Test deployment report (one-time)
source venv/bin/activate
export MATRIX_BOT_PASSWORD="your-password"
python3 deploy/matrix-agent.py report

# Test feedback listener (continuous)
python3 deploy/matrix-agent.py listen
```

## Architecture

### Two Modes

1. **Report Mode** (`report`): One-time deployment announcement
   - Called automatically after each deployment
   - Rate-limited to prevent spam

2. **Listen Mode** (`listen`): Continuous feedback monitoring
   - Runs as systemd service
   - Auto-restarts on failure
   - Saves feedback for processing

### Feedback Processing Pipeline

```
User Message → Security Validation → Save to JSONL → (Future) Create Issue
                      ↓
               Block if malicious
```

Saved feedback format:
```json
{
  "timestamp": "2025-12-06T17:30:00",
  "sender": "@user:themultiverse.school",
  "message": "Feature request: add dark mode",
  "is_safe": true,
  "rejection_reason": null,
  "processed": false
}
```

### Future Enhancement: Issue Creation

A separate agent can process `feedback/matrix-feedback.jsonl`:
- Read unprocessed safe feedback
- Use Claude Code to analyze and create GitHub issues
- Mark feedback as processed
- Run periodically via cron

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `HOMESERVER` | `https://matrix.themultiverse.school` | Matrix homeserver URL |
| `REGISTRATION_TOKEN` | `multiversemultiswarm` | Registration token for bot account |
| `BOT_USERNAME` | `llm-tutor-agent` | Bot account username |
| `MATRIX_BOT_PASSWORD` | `llm-tutor-2024` | Bot password (set via env var) |
| `CHANNEL_ROOM_ID` | `#agentic-sdlc:themultiverse.school` | Channel to monitor |

## Monitoring

```bash
# Check listener service status
sudo systemctl status matrix-listener

# View listener logs
sudo journalctl -u matrix-listener -f

# View recent feedback
tail -f feedback/matrix-feedback.jsonl

# Check last deployment report
cat .matrix-state.json
```

## Registration

The bot registers using token-based authentication (MSC3231):
- Registration token: `multiversemultiswarm`
- Account: `@llm-tutor-agent:themultiverse.school`

On first run, it will register the account. Subsequent runs will login with the password.

## Sources

Based on:
- [Matrix.org - matrix-nio documentation](https://matrix.org/docs/older/python-nio/)
- [matrix-nio examples](https://matrix-nio.readthedocs.io/en/latest/examples.html)
- [nio-template bot template](https://github.com/anoadragon453/nio-template)
- [MSC3231: Token-based registration](https://github.com/matrix-org/matrix-spec-proposals/blob/main/proposals/3231-token-authenticated-registration.md)
- [matrix-registration-bot](https://github.com/moan0s/matrix-registration-bot)
