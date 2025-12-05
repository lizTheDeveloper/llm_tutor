#!/bin/bash

# VM Bootstrap Script - Runs on first boot of GCP VM
# Sets up the entire autonomous development environment

set -e
exec > >(tee -a /var/log/bootstrap.log)
exec 2>&1

echo "=================================================="
echo "Autonomous Development VM Bootstrap"
echo "Started at: $(date)"
echo "=================================================="

# Update system
echo "Updating system packages..."
apt-get update
apt-get upgrade -y

# Pre-configure postfix to avoid interactive prompts
echo "Pre-configuring Postfix..."
echo "postfix postfix/mailname string llmtutor.dev" | debconf-set-selections
echo "postfix postfix/main_mailer_type string 'Internet Site'" | debconf-set-selections
export DEBIAN_FRONTEND=noninteractive

# Install basic dependencies
echo "Installing dependencies..."
apt-get install -y \
    git \
    curl \
    wget \
    build-essential \
    python3.11 \
    python3.11-venv \
    python3-pip \
    postgresql \
    postgresql-contrib \
    redis-server \
    nginx \
    mailutils \
    postfix \
    jq

# Install Node.js (for frontend)
echo "Installing Node.js..."
curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
apt-get install -y nodejs

# Create user for running the app
echo "Creating llmtutor user..."
useradd -m -s /bin/bash llmtutor || true
usermod -aG sudo llmtutor

# Install Claude CLI
echo "Installing Claude CLI..."
su - llmtutor -c "curl -fsSL https://claude.ai/install.sh | bash"
# Add to PATH
echo 'export PATH="$HOME/.local/bin:$PATH"' >> /home/llmtutor/.bashrc
echo 'export PATH="$HOME/.local/bin:$PATH"' >> /home/llmtutor/.profile

# Clone repository
echo "Cloning repository..."
su - llmtutor -c "
    cd /home/llmtutor
    if [ ! -d llm_tutor ]; then
        git clone https://github.com/lizTheDeveloper/llm_tutor.git
    fi
    cd llm_tutor
    git config user.name 'Autonomous Dev System'
    git config user.email 'autonomous@llmtutor.dev'
"

# Set up Python environment
echo "Setting up Python environment..."
su - llmtutor -c "
    cd /home/llmtutor/llm_tutor
    python3.11 -m venv venv
    source venv/bin/activate
    pip install --upgrade pip
    pip install -r backend/requirements.txt
"

# Set up PostgreSQL
echo "Configuring PostgreSQL..."
sudo -u postgres psql <<EOF
CREATE USER llmtutor WITH PASSWORD 'change_this_password';
CREATE DATABASE llm_tutor_dev OWNER llmtutor;
GRANT ALL PRIVILEGES ON DATABASE llm_tutor_dev TO llmtutor;
EOF

# Set up cron jobs
echo "Setting up cron jobs..."
su - llmtutor -c "
    crontab <<CRON
# Autonomous Development System Cron Jobs

# TDD Agent - Every 30 minutes
*/30 * * * * /home/llmtutor/llm_tutor/autonomous-agent.sh >> /home/llmtutor/llm_tutor/agent-logs/cron-tdd.log 2>&1

# Reviewer Agent - Every hour
0 * * * * /home/llmtutor/llm_tutor/autonomous-reviewer.sh >> /home/llmtutor/llm_tutor/agent-logs/cron-reviewer.log 2>&1

# Summary Agent - Every 4 hours
0 */4 * * * /home/llmtutor/llm_tutor/autonomous-summary.sh >> /home/llmtutor/llm_tutor/agent-logs/cron-summary.log 2>&1

CRON
"

# Create systemd service for monitoring
echo "Creating systemd service..."
cat > /etc/systemd/system/autonomous-agents.service <<EOF
[Unit]
Description=Autonomous Development Agents
After=network.target postgresql.service redis.service

[Service]
Type=oneshot
User=llmtutor
WorkingDirectory=/home/llmtutor/llm_tutor
ExecStart=/bin/bash -c "echo 'Autonomous agents managed by cron'"
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable autonomous-agents.service

# Configure email (basic postfix setup)
echo "Configuring email..."
debconf-set-selections <<< "postfix postfix/mailname string llmtutor.dev"
debconf-set-selections <<< "postfix postfix/main_mailer_type string 'Internet Site'"
systemctl restart postfix

echo "=================================================="
echo "Bootstrap completed at: $(date)"
echo "=================================================="
echo ""
echo "Next steps:"
echo "1. Configure secrets in /home/llmtutor/llm_tutor/.env"
echo "2. Set up Claude CLI authentication"
echo "3. Configure email settings"
echo "4. Test agents manually before relying on cron"
