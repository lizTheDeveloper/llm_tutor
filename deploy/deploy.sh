#!/bin/bash

# Auto-deployment script for LLM Tutor
# This script runs on the VM to deploy the latest code

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "=================================================="
echo "LLM Tutor Auto-Deployment"
echo "Started at: $(date)"
echo "=================================================="

cd "$PROJECT_ROOT"

# Pull latest code
echo "Pulling latest code from main..."
git fetch origin
git reset --hard origin/main

# Backend deployment
echo ""
echo "Deploying backend..."
cd backend

# Activate virtual environment
source ../venv/bin/activate

# Install/update dependencies
pip install -q --upgrade pip
pip install -q -r requirements.txt

# Run database migrations if they exist
if [ -d "migrations" ]; then
    echo "Running database migrations..."
    alembic upgrade head || echo "No migrations to run"
fi

# Restart backend service (if running as systemd service)
if systemctl is-active --quiet llm-tutor-backend 2>/dev/null; then
    echo "Restarting backend service..."
    sudo systemctl restart llm-tutor-backend
else
    echo "Backend service not found - skipping restart"
fi

# Frontend deployment
echo ""
echo "Deploying frontend..."
cd "$PROJECT_ROOT/frontend"

# Install dependencies
npm install --silent

# Build frontend
npm run build

# Copy build to nginx web root (if configured)
if [ -d "/var/www/llm-tutor" ]; then
    echo "Copying frontend build to web root..."
    sudo rm -rf /var/www/llm-tutor/*
    sudo cp -r build/* /var/www/llm-tutor/
    sudo chown -R www-data:www-data /var/www/llm-tutor
fi

# Reload nginx
if systemctl is-active --quiet nginx 2>/dev/null; then
    echo "Reloading nginx..."
    sudo systemctl reload nginx
fi

echo ""
echo "=================================================="
echo "Deployment completed at: $(date)"
echo "=================================================="
echo ""
echo "Deployed commit:"
git log -1 --oneline
