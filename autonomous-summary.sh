#!/bin/bash

# Autonomous Summary - Generates and emails 4-hour development summaries
# This script will:
# 1. Launch Claude Code with the autonomous-summary agent
# 2. Generate comprehensive summary of recent activity
# 3. Email summary to stakeholders
# 4. Commit summary artifact

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="$SCRIPT_DIR/agent-logs"
SUMMARY_DIR="$SCRIPT_DIR/summaries"
mkdir -p "$LOG_DIR"
mkdir -p "$SUMMARY_DIR"
LOG_FILE="$LOG_DIR/autonomous-summary-$(date +%Y%m%d-%H%M%S).log"

# Load environment variables if .env exists
if [ -f "$SCRIPT_DIR/.env" ]; then
    export $(grep -v '^#' "$SCRIPT_DIR/.env" | xargs)
fi

# Default email settings
SUMMARY_EMAIL_RECIPIENTS="${SUMMARY_EMAIL_RECIPIENTS:-admin@example.com}"
SUMMARY_EMAIL_FROM="${SUMMARY_EMAIL_FROM:-autonomous@llmtutor.dev}"

echo "==================================================================" | tee -a "$LOG_FILE"
echo "Autonomous Summary - Starting at $(date)" | tee -a "$LOG_FILE"
echo "==================================================================" | tee -a "$LOG_FILE"
echo "Email Recipients: $SUMMARY_EMAIL_RECIPIENTS" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

# Phase 1: Generate Summary Report
echo "Phase 1: Generating Summary Report..." | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

claude \
  --print \
  --dangerously-skip-permissions \
  "Use the autonomous-summary agent to generate a comprehensive 4-hour development summary. Review all git commits, agent logs, review reports, and roadmap updates from the past 4 hours. Generate a detailed email summary and save it to summaries/ directory. Include all metrics, completed work, issues found, and next steps." \
  2>&1 | tee -a "$LOG_FILE"

SUMMARY_EXIT_CODE=${PIPESTATUS[0]}

echo "" | tee -a "$LOG_FILE"
echo "Summary generation completed with exit code: $SUMMARY_EXIT_CODE" | tee -a "$LOG_FILE"

# Phase 2: Save Summary for Viewing
echo "" | tee -a "$LOG_FILE"
echo "Phase 2: Saving Summary..." | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

cd "$SCRIPT_DIR"

# Find the most recent summary file
LATEST_SUMMARY=$(ls -t summaries/summary-*.txt 2>/dev/null | head -1)

if [ -n "$LATEST_SUMMARY" ] && [ -f "$LATEST_SUMMARY" ]; then
    echo "Found summary: $LATEST_SUMMARY" | tee -a "$LOG_FILE"

    # Create a "latest" symlink for easy access
    ln -sf "$(basename "$LATEST_SUMMARY")" summaries/latest-summary.txt

    # Also copy to a web-accessible location if nginx is set up
    if [ -d "/var/www/html" ]; then
        sudo cp "$LATEST_SUMMARY" /var/www/html/latest-summary.txt 2>/dev/null || true
    fi

    echo "✓ Summary saved and accessible at:" | tee -a "$LOG_FILE"
    echo "  - $LATEST_SUMMARY" | tee -a "$LOG_FILE"
    echo "  - summaries/latest-summary.txt (symlink)" | tee -a "$LOG_FILE"
    echo "  - http://34.28.81.46/latest-summary.txt (if nginx configured)" | tee -a "$LOG_FILE"

    # Display summary header
    echo "" | tee -a "$LOG_FILE"
    echo "Summary Preview:" | tee -a "$LOG_FILE"
    head -20 "$LATEST_SUMMARY" | tee -a "$LOG_FILE"
else
    echo "✗ No summary file found!" | tee -a "$LOG_FILE"
fi

# Phase 3: Commit Summary Artifacts
echo "" | tee -a "$LOG_FILE"
echo "Phase 3: Committing Summary Artifacts..." | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

if ! git diff-index --quiet HEAD -- 2>/dev/null; then
    echo "Uncommitted changes detected. Auto-committing summary..." | tee -a "$LOG_FILE"

    claude \
      --print \
      --dangerously-skip-permissions \
      "There are uncommitted changes from the summary generation. Please commit the summary report with an appropriate commit message." \
      2>&1 | tee -a "$LOG_FILE"

    COMMIT_EXIT_CODE=${PIPESTATUS[0]}
    echo "" | tee -a "$LOG_FILE"
    echo "Auto-commit completed with exit code: $COMMIT_EXIT_CODE" | tee -a "$LOG_FILE"
else
    echo "All summary artifacts already committed." | tee -a "$LOG_FILE"
fi

echo "" | tee -a "$LOG_FILE"
echo "==================================================================" | tee -a "$LOG_FILE"
echo "Autonomous Summary - Completed at $(date)" | tee -a "$LOG_FILE"
echo "==================================================================" | tee -a "$LOG_FILE"

# Show summary preview
if [ -n "$LATEST_SUMMARY" ] && [ -f "$LATEST_SUMMARY" ]; then
    echo "" | tee -a "$LOG_FILE"
    echo "Summary Preview:" | tee -a "$LOG_FILE"
    echo "-------------------------------------------------------------------" | tee -a "$LOG_FILE"
    head -50 "$LATEST_SUMMARY" | tee -a "$LOG_FILE"
    echo "-------------------------------------------------------------------" | tee -a "$LOG_FILE"
fi

echo "" | tee -a "$LOG_FILE"
echo "Full execution log saved to: $LOG_FILE"
