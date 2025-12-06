#!/bin/bash

# Autonomous Agent - Launches Claude Code in headless mode to complete OpenSpec change proposals using TDD workflow
# This script will:
# 1. List available OpenSpec change proposals
# 2. Launch Claude Code with the TDD agent to implement the next proposal
# 3. Update the proposal's tasks.md checklist as work progresses
# 4. Auto-commit any changes if the working tree is dirty
# 5. Update the roadmap to reflect completed work

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="$SCRIPT_DIR/agent-logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/autonomous-agent-$(date +%Y%m%d-%H%M%S).log"

echo "==================================================================" | tee -a "$LOG_FILE"
echo "Autonomous Agent - Starting at $(date)" | tee -a "$LOG_FILE"
echo "==================================================================" | tee -a "$LOG_FILE"

# Phase 0: List available OpenSpec change proposals
echo "" | tee -a "$LOG_FILE"
echo "Phase 0: Checking OpenSpec change proposals..." | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

cd "$SCRIPT_DIR"
openspec list 2>&1 | tee -a "$LOG_FILE"

echo "" | tee -a "$LOG_FILE"

# Phase 1: Execute TDD workflow for next OpenSpec change proposal
echo "" | tee -a "$LOG_FILE"
echo "Phase 1: Launching TDD Workflow Engineer with OpenSpec integration..." | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

claude \
  --print \
  --dangerously-skip-permissions \
  "Use the tdd-workflow-engineer agent to implement the next OpenSpec change proposal. Follow these steps:

1. Run 'openspec list' to see available change proposals
2. Choose the highest priority proposal (C5 first, then D1, D2, D3, D4 in order)
3. Run 'openspec show <change-id>' to read the full proposal
4. Read the proposal.md to understand the 'why' and 'what'
5. Read the specs/<capability>/spec.md to understand requirements and scenarios
6. Read the tasks.md to get the implementation checklist
7. Implement the change following TDD workflow rigorously
8. As you complete tasks, update tasks.md to check off completed items (- [x])
9. Follow all phases of the TDD workflow from start to finish
10. Update plans/roadmap.md to mark the work stream as complete when done

Reference: openspec/AGENTS.md for OpenSpec workflow details" \
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
    "The working tree has uncommitted changes from the autonomous TDD workflow. Please review all changes, including any updated OpenSpec tasks.md files, create an appropriate commit message following the project's commit message format (see the TDD agent's Phase 7 commit format in frontend/.claude/agents/tdd-workflow-engineer.md), and commit the changes. Use git status, git diff, and examine the modified files to understand what was changed." \
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
    "Use the project-manager agent to review the most recent commit and update plans/roadmap.md accordingly. Check which OpenSpec change proposal was worked on (use 'openspec list' or check git diff for openspec/changes/*/tasks.md), mark the corresponding work stream in the roadmap as complete with timestamp if all tasks are done, update status indicators, and ensure the roadmap accurately reflects the current project state. After updating the roadmap, commit the changes." \
    2>&1 | tee -a "$LOG_FILE"

  ROADMAP_UPDATE_EXIT_CODE=${PIPESTATUS[0]}
  echo "" | tee -a "$LOG_FILE"
  echo "Roadmap update completed with exit code: $ROADMAP_UPDATE_EXIT_CODE" | tee -a "$LOG_FILE"
else
  echo "Roadmap was already updated. Skipping project-manager phase." | tee -a "$LOG_FILE"
fi

# Phase 4: Check if proposal should be archived
echo "" | tee -a "$LOG_FILE"
echo "Phase 4: Checking if any OpenSpec proposals are complete and ready to archive..." | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

# List current proposals with task counts
openspec list 2>&1 | tee -a "$LOG_FILE"

echo "" | tee -a "$LOG_FILE"
echo "Note: When a proposal shows all tasks complete (e.g., 39/39), use 'openspec archive <change-id>' to move it to archive/" | tee -a "$LOG_FILE"
echo "Archive command example: openspec archive add-chat-interface-ui --yes" | tee -a "$LOG_FILE"

echo "" | tee -a "$LOG_FILE"
echo "==================================================================" | tee -a "$LOG_FILE"
echo "Autonomous Agent - Completed at $(date)" | tee -a "$LOG_FILE"
echo "==================================================================" | tee -a "$LOG_FILE"

# Show final status
echo "" | tee -a "$LOG_FILE"
echo "Final Git Status:" | tee -a "$LOG_FILE"
git status | tee -a "$LOG_FILE"

echo "" | tee -a "$LOG_FILE"
echo "OpenSpec Status:" | tee -a "$LOG_FILE"
openspec list 2>&1 | tee -a "$LOG_FILE"

echo "" | tee -a "$LOG_FILE"
echo "Full execution log saved to: $LOG_FILE"
