#!/bin/bash

# Setup systemd services and nginx for auto-deployment
# Run this once on the VM to enable auto-deployment

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "=================================================="
echo "Setting up deployment services"
echo "=================================================="

# Create backend systemd service
echo "Creating backend systemd service..."
sudo tee /etc/systemd/system/llm-tutor-backend.service > /dev/null <<EOF
[Unit]
Description=LLM Tutor Backend API
After=network.target postgresql.service redis.service

[Service]
Type=simple
User=llmtutor
WorkingDirectory=/home/llmtutor/llm_tutor/backend
Environment="PATH=/home/llmtutor/llm_tutor/venv/bin:/usr/local/bin:/usr/bin:/bin"
ExecStart=/home/llmtutor/llm_tutor/venv/bin/hypercorn app:app --bind 0.0.0.0:8000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Configure nginx for frontend
echo "Configuring nginx for frontend..."
sudo mkdir -p /var/www/llm-tutor
sudo chown -R www-data:www-data /var/www/llm-tutor

sudo tee /etc/nginx/sites-available/llm-tutor > /dev/null <<'EOF'
server {
    listen 80;
    server_name _;

    # Frontend
    location / {
        root /var/www/llm-tutor;
        try_files \$uri \$uri/ /index.html;
        add_header Cache-Control "no-cache, must-revalidate";
    }

    # Backend API
    location /api/ {
        proxy_pass http://localhost:8000/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host \$host;
        proxy_cache_bypass \$http_upgrade;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    # Health check endpoint
    location /health {
        proxy_pass http://localhost:8000/health;
    }
}
EOF

# Enable nginx site
sudo ln -sf /etc/nginx/sites-available/llm-tutor /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default

# Test nginx config
sudo nginx -t

# Reload services
echo "Enabling and starting services..."
sudo systemctl daemon-reload
sudo systemctl enable llm-tutor-backend
sudo systemctl start llm-tutor-backend
sudo systemctl reload nginx

echo ""
echo "=================================================="
echo "Services configured successfully!"
echo "=================================================="
echo ""
echo "Services status:"
sudo systemctl status llm-tutor-backend --no-pager | head -10
sudo systemctl status nginx --no-pager | head -10
echo ""
echo "Backend API: http://34.88.245.170/api/"
echo "Frontend: http://34.88.245.170/"
echo "Health: http://34.88.245.170/health"
