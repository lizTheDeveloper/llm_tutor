#!/bin/bash
# VM Startup Script for CodeMentor
# This script runs when the VM first boots or restarts

set -e

echo "Starting CodeMentor VM setup..."

# Update system packages
echo "Updating system packages..."
apt-get update
apt-get upgrade -y

# Install required packages
echo "Installing required packages..."
apt-get install -y \
    apt-transport-https \
    ca-certificates \
    curl \
    gnupg \
    lsb-release \
    git \
    python3.11 \
    python3.11-venv \
    python3-pip \
    nginx \
    supervisor

# Install Docker
echo "Installing Docker..."
if ! command -v docker &> /dev/null; then
    curl -fsSL https://get.docker.com -o get-docker.sh
    sh get-docker.sh
    rm get-docker.sh
    systemctl enable docker
    systemctl start docker
fi

# Create application directory
APP_DIR="/opt/codementor"
mkdir -p "${APP_DIR}"
cd "${APP_DIR}"

# Create environment file from metadata
echo "Setting up environment variables..."
cat > "${APP_DIR}/.env" << 'EOF'
# Environment variables for CodeMentor backend
ENVIRONMENT=production
PORT=5000

# Database connection (from Secret Manager)
DATABASE_URL=${DATABASE_URL}

# Redis connection (from Secret Manager)
REDIS_URL=${REDIS_URL}

# JWT Secret
JWT_SECRET=${JWT_SECRET}

# LLM API Keys
GROQ_API_KEY=${GROQ_API_KEY}

# OAuth
GITHUB_CLIENT_ID=${GITHUB_CLIENT_ID}
GITHUB_CLIENT_SECRET=${GITHUB_CLIENT_SECRET}
GOOGLE_CLIENT_ID=${GOOGLE_CLIENT_ID}
GOOGLE_CLIENT_SECRET=${GOOGLE_CLIENT_SECRET}

# Email service (if using SendGrid)
SENDGRID_API_KEY=${SENDGRID_API_KEY}
FROM_EMAIL=${FROM_EMAIL}
EOF

# Fetch secrets from Secret Manager if available
if command -v gcloud &> /dev/null; then
    PROJECT_ID=$(gcloud config get-value project 2>/dev/null)

    # Function to fetch secret
    fetch_secret() {
        local secret_name=$1
        local env_var=$2
        if gcloud secrets describe "${secret_name}" --project="${PROJECT_ID}" &> /dev/null; then
            local value=$(gcloud secrets versions access latest --secret="${secret_name}" --project="${PROJECT_ID}" 2>/dev/null)
            if [ -n "${value}" ]; then
                sed -i "s|^${env_var}=.*|${env_var}=${value}|g" "${APP_DIR}/.env"
            fi
        fi
    }

    # Fetch all secrets
    fetch_secret "database-url" "DATABASE_URL"
    fetch_secret "redis-url" "REDIS_URL"
    fetch_secret "jwt-secret" "JWT_SECRET"
    fetch_secret "groq-api-key" "GROQ_API_KEY"
fi

# Configure Nginx as reverse proxy
echo "Configuring Nginx..."
cat > /etc/nginx/sites-available/codementor << 'EOF'
server {
    listen 80;
    server_name _;

    client_max_body_size 10M;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # WebSocket support (if needed)
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";

        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    location /health {
        proxy_pass http://127.0.0.1:5000/health;
        access_log off;
    }
}
EOF

ln -sf /etc/nginx/sites-available/codementor /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl restart nginx

# Create systemd service for the application
echo "Creating systemd service..."
cat > /etc/systemd/system/codementor.service << EOF
[Unit]
Description=CodeMentor Backend Service
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=${APP_DIR}
EnvironmentFile=${APP_DIR}/.env
ExecStart=/usr/bin/python3.11 ${APP_DIR}/app.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Enable but don't start yet (application code not deployed)
systemctl daemon-reload
systemctl enable codementor.service

echo "✓ VM setup complete!"
echo "Ready for application deployment"
echo ""
echo "To deploy the application:"
echo "1. Copy application code to ${APP_DIR}"
echo "2. Install Python dependencies"
echo "3. Start service: systemctl start codementor"
