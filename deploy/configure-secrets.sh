#!/bin/bash

# Configure Secrets for Autonomous Development VM
# Run this script after SSH'ing into the VM for the first time

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "=================================================="
echo "Configure Secrets for Autonomous Development"
echo "=================================================="
echo ""

# Create .env file
cat > "$PROJECT_ROOT/.env" <<EOF
# Autonomous Development System Configuration

# NOTE: Claude CLI uses your Claude Pro subscription - no API key needed!
# Just run: claude setup-token

# OpenAI API Key (for embeddings - optional, only if using embeddings)
# OPENAI_API_KEY="sk-..."

# Database
DATABASE_URL="postgresql://llmtutor:$(openssl rand -hex 16)@localhost/llm_tutor_dev"

# Redis
REDIS_URL="redis://localhost:6379/0"

# JWT Secret
JWT_SECRET="$(openssl rand -hex 32)"

# Environment
ENVIRONMENT="production"

# VM Info
VM_IP="34.28.81.46"
EOF

echo "Created .env file at: $PROJECT_ROOT/.env"
echo ""
echo "⚠️  IMPORTANT: Please edit the .env file and update:"
echo "   1. SUMMARY_EMAIL_RECIPIENTS - your email address"
echo "   2. OPENAI_API_KEY - your OpenAI API key"
echo "   3. DATABASE_URL password - change 'change_this_password'"
echo ""
echo "Edit now? (y/N)"
read -r response

if [[ "$response" =~ ^[Yy]$ ]]; then
    ${EDITOR:-nano} "$PROJECT_ROOT/.env"
fi

# Set up Claude CLI authentication
echo ""
echo "=================================================="
echo "Setting up Claude CLI Authentication"
echo "=================================================="
echo ""
echo "Please run: claude setup-token"
echo "Then follow the prompts to authenticate."
echo ""

# Set up Git credentials
echo "=================================================="
echo "Setting up Git Credentials"
echo "=================================================="
echo ""
echo "Please configure git for commits:"
echo "  git config --global user.name 'Autonomous Dev System'"
echo "  git config --global user.email 'autonomous@llmtutor.dev'"
echo ""

# Set up GitHub SSH key (optional)
echo "=================================================="
echo "GitHub SSH Key (Optional)"
echo "=================================================="
echo ""
echo "To enable git push, you'll need to:"
echo "  1. Generate SSH key: ssh-keygen -t ed25519 -C 'autonomous@llmtutor.dev'"
echo "  2. Add to GitHub: cat ~/.ssh/id_ed25519.pub"
echo "  3. Test: ssh -T git@github.com"
echo ""

echo "Configuration guide complete!"
echo ""
echo "Next steps:"
echo "  1. Finish editing .env file"
echo "  2. Run: claude setup-token"
echo "  3. Test agents manually before relying on cron"
echo "  4. Monitor logs: tail -f agent-logs/*.log"
