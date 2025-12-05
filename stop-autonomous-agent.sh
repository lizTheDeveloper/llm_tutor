#!/bin/bash

# Stop Autonomous Agents - Unloads all autonomous launchd tasks

echo "Stopping autonomous agent launchd tasks..."

# Stop TDD agent
launchctl unload /Users/annhoward/Library/LaunchAgents/com.llmtutor.autonomous-agent.plist
echo "✓ TDD agent stopped"

# Stop reviewer agent
launchctl unload /Users/annhoward/Library/LaunchAgents/com.llmtutor.autonomous-reviewer.plist
echo "✓ Reviewer agent stopped"

echo ""
echo "All autonomous agents stopped at $(date)"
echo "Tasks unloaded successfully."
