#!/bin/bash

# Stop Autonomous Agent - Unloads the launchd task

echo "Stopping autonomous agent launchd task..."
launchctl unload /Users/annhoward/Library/LaunchAgents/com.llmtutor.autonomous-agent.plist

echo "Autonomous agent stopped at $(date)"
echo "Task unloaded successfully."
