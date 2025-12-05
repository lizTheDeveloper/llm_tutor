#!/bin/bash

# Autonomous Agent - Launches Claude Code in headless mode to complete roadmap tasks using TDD workflow
# This script will:
# 1. Launch Claude Code with the TDD agent to complete the next roadmap task
# 2. Auto-commit any changes if the working tree is dirty

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="$SCRIPT_DIR/agent-logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/autonomous-agent-$(date +%Y%m%d-%H%M%S).log"

echo "==================================================================" | tee -a "$LOG_FILE"
echo "Autonomous Agent - Starting at $(date)" | tee -a "$LOG_FILE"
echo "==================================================================" | tee -a "$LOG_FILE"

# Phase 1: Execute TDD workflow for next roadmap task
echo "" | tee -a "$LOG_FILE"
echo "Phase 1: Launching TDD Workflow Engineer..." | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

claude \
  --print \
  --dangerously-skip-permissions \
  "Use the tdd-workflow-engineer agent to identify, claim, and complete the next available unclaimed work stream from plans/roadmap.md. Follow all phases of the TDD workflow rigorously from start to finish." \
  2>&1 | tee -a "$LOG_FILE"

TDD_EXIT_CODE=${PIPESTATUS[0]}

echo "" | tee -a "$LOG_FILE"
echo "TDD workflow completed with exit code: $TDD_EXIT_CODE" | tee -a "$LOG_FILE"

# Phase 2: Check for uncommitted changes and auto-commit
echo "" | tee -a "$LOG_FILE"
echo "Phase 2: Checking for uncommitted changes..." | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

cd "$SCRIPT_DIR"

if ! git diff-index --quiet HEAD -- 2>/dev/null; then
  echo "Working tree is dirty. Launching Claude Code to generate commit..." | tee -a "$LOG_FILE"
  echo "" | tee -a "$LOG_FILE"

  claude \
    --print \
    --dangerously-skip-permissions \
    "The working tree has uncommitted changes from the autonomous TDD workflow. Please review all changes, create an appropriate commit message following the project's commit message format (see the TDD agent's Phase 7 commit format in frontend/.claude/agents/tdd-workflow-engineer.md), and commit the changes. Use git status, git diff, and examine the modified files to understand what was changed." \
    2>&1 | tee -a "$LOG_FILE"

  COMMIT_EXIT_CODE=${PIPESTATUS[0]}
  echo "" | tee -a "$LOG_FILE"
  echo "Auto-commit completed with exit code: $COMMIT_EXIT_CODE" | tee -a "$LOG_FILE"
else
  echo "Working tree is clean. No commit needed." | tee -a "$LOG_FILE"
fi

# Phase 3: Verify roadmap was updated, if not use project-manager to update it
echo "" | tee -a "$LOG_FILE"
echo "Phase 3: Checking if roadmap was updated..." | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

# Check if roadmap was modified in the most recent commit or working tree
ROADMAP_MODIFIED=false

# Check if roadmap is in the most recent commit
if git diff HEAD~1 HEAD --name-only 2>/dev/null | grep -q "plans/roadmap.md"; then
  ROADMAP_MODIFIED=true
  echo "Roadmap was updated in the last commit." | tee -a "$LOG_FILE"
# Check if roadmap has uncommitted changes
elif git diff --name-only 2>/dev/null | grep -q "plans/roadmap.md"; then
  ROADMAP_MODIFIED=true
  echo "Roadmap has uncommitted changes." | tee -a "$LOG_FILE"
elif git diff --cached --name-only 2>/dev/null | grep -q "plans/roadmap.md"; then
  ROADMAP_MODIFIED=true
  echo "Roadmap has staged changes." | tee -a "$LOG_FILE"
fi

if [ "$ROADMAP_MODIFIED" = false ]; then
  echo "Roadmap was NOT updated. Launching project-manager to update it..." | tee -a "$LOG_FILE"
  echo "" | tee -a "$LOG_FILE"

  claude \
    --print \
    --dangerously-skip-permissions \
    "Use the project-manager agent to review the most recent commit and update plans/roadmap.md accordingly. Mark the completed work stream as complete with timestamp, update status indicators, and ensure the roadmap accurately reflects the current project state. After updating the roadmap, commit the changes." \
    2>&1 | tee -a "$LOG_FILE"

  ROADMAP_UPDATE_EXIT_CODE=${PIPESTATUS[0]}
  echo "" | tee -a "$LOG_FILE"
  echo "Roadmap update completed with exit code: $ROADMAP_UPDATE_EXIT_CODE" | tee -a "$LOG_FILE"
else
  echo "Roadmap was already updated. Skipping project-manager phase." | tee -a "$LOG_FILE"
fi

echo "" | tee -a "$LOG_FILE"
echo "==================================================================" | tee -a "$LOG_FILE"
echo "Autonomous Agent - Completed at $(date)" | tee -a "$LOG_FILE"
echo "==================================================================" | tee -a "$LOG_FILE"

# Show final status
echo "" | tee -a "$LOG_FILE"
echo "Final Git Status:" | tee -a "$LOG_FILE"
git status | tee -a "$LOG_FILE"

echo "" | tee -a "$LOG_FILE"
echo "Full execution log saved to: $LOG_FILE"
