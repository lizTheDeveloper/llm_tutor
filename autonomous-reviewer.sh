#!/bin/bash

# Autonomous Reviewer - Launches Claude Code to perform architectural reviews
# This script will:
# 1. Launch Claude Code with the autonomous-reviewer agent
# 2. Review will update anti-pattern checklist and create review report
# 3. Critical issues will be escalated to roadmap via project-manager
# 4. All artifacts will be auto-committed

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="$SCRIPT_DIR/agent-logs"
REVIEW_DIR="$SCRIPT_DIR/reviews"
mkdir -p "$LOG_DIR"
mkdir -p "$REVIEW_DIR"
LOG_FILE="$LOG_DIR/autonomous-reviewer-$(date +%Y%m%d-%H%M%S).log"

echo "==================================================================" | tee -a "$LOG_FILE"
echo "Autonomous Reviewer - Starting at $(date)" | tee -a "$LOG_FILE"
echo "==================================================================" | tee -a "$LOG_FILE"

# Phase 1: Execute Architectural Review
echo "" | tee -a "$LOG_FILE"
echo "Phase 1: Launching Autonomous Reviewer..." | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

claude \
  --print \
  --dangerously-skip-permissions \
  "Use the autonomous-reviewer agent to perform a comprehensive architectural review of the codebase. Follow all 6 phases: initialize review, perform comprehensive review, update anti-pattern checklist, generate review report, escalate critical issues to roadmap via project-manager, and commit all review artifacts." \
  2>&1 | tee -a "$LOG_FILE"

REVIEW_EXIT_CODE=${PIPESTATUS[0]}

echo "" | tee -a "$LOG_FILE"
echo "Architectural review completed with exit code: $REVIEW_EXIT_CODE" | tee -a "$LOG_FILE"

# Phase 2: Verify artifacts were created and committed
echo "" | tee -a "$LOG_FILE"
echo "Phase 2: Verifying review artifacts..." | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

cd "$SCRIPT_DIR"

# Check if review report was created
LATEST_REVIEW=$(ls -t reviews/review-*.md 2>/dev/null | head -1)
if [ -n "$LATEST_REVIEW" ]; then
  echo "Review report created: $LATEST_REVIEW" | tee -a "$LOG_FILE"
else
  echo "WARNING: No review report found!" | tee -a "$LOG_FILE"
fi

# Check if anti-pattern checklist exists
if [ -f "reviews/anti-pattern-checklist.md" ]; then
  PATTERN_COUNT=$(grep -c "^### " reviews/anti-pattern-checklist.md 2>/dev/null || echo "0")
  echo "Anti-pattern checklist exists with $PATTERN_COUNT patterns" | tee -a "$LOG_FILE"
else
  echo "WARNING: Anti-pattern checklist not found!" | tee -a "$LOG_FILE"
fi

# Check for uncommitted changes and commit if necessary
if ! git diff-index --quiet HEAD -- 2>/dev/null; then
  echo "Uncommitted changes detected. Auto-committing review artifacts..." | tee -a "$LOG_FILE"
  echo "" | tee -a "$LOG_FILE"

  claude \
    --print \
    --dangerously-skip-permissions \
    "There are uncommitted changes from the architectural review. Please commit all review artifacts (review reports, anti-pattern checklist, and any roadmap updates) with an appropriate commit message." \
    2>&1 | tee -a "$LOG_FILE"

  COMMIT_EXIT_CODE=${PIPESTATUS[0]}
  echo "" | tee -a "$LOG_FILE"
  echo "Auto-commit completed with exit code: $COMMIT_EXIT_CODE" | tee -a "$LOG_FILE"
else
  echo "All review artifacts already committed." | tee -a "$LOG_FILE"
fi

echo "" | tee -a "$LOG_FILE"
echo "==================================================================" | tee -a "$LOG_FILE"
echo "Autonomous Reviewer - Completed at $(date)" | tee -a "$LOG_FILE"
echo "==================================================================" | tee -a "$LOG_FILE"

# Show final status
echo "" | tee -a "$LOG_FILE"
echo "Final Git Status:" | tee -a "$LOG_FILE"
git status | tee -a "$LOG_FILE"

echo "" | tee -a "$LOG_FILE"
echo "Review Summary:" | tee -a "$LOG_FILE"
if [ -n "$LATEST_REVIEW" ]; then
  echo "Latest Review: $LATEST_REVIEW" | tee -a "$LOG_FILE"
  echo "" | tee -a "$LOG_FILE"
  head -30 "$LATEST_REVIEW" | tee -a "$LOG_FILE"
fi

echo "" | tee -a "$LOG_FILE"
echo "Full execution log saved to: $LOG_FILE"
