#!/bin/bash
# Setup Matrix communications agent on the VM

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "=================================================="
echo "Setting up Matrix Communications Agent"
echo "=================================================="

# Install matrix-nio in venv
echo "Installing matrix-nio..."
cd "$PROJECT_ROOT"
source venv/bin/activate
pip install -q -r deploy/matrix-requirements.txt

# Create systemd service for listener (continuous)
echo "Creating Matrix listener service..."
sudo tee /etc/systemd/system/matrix-listener.service > /dev/null <<EOF
[Unit]
Description=Matrix Communications Agent - Feedback Listener
After=network.target

[Service]
Type=simple
User=llmtutor
WorkingDirectory=/home/llmtutor/llm_tutor
Environment="PATH=/home/llmtutor/llm_tutor/venv/bin:/usr/local/bin:/usr/bin:/bin"
Environment="MATRIX_BOT_PASSWORD=${MATRIX_BOT_PASSWORD:-llm-tutor-2024}"
ExecStart=/home/llmtutor/llm_tutor/venv/bin/python3 /home/llmtutor/llm_tutor/deploy/matrix-agent.py listen
Restart=always
RestartSec=30

[Install]
WantedBy=multi-user.target
EOF

# Create deployment reporter script (called after deployments)
cat > "$PROJECT_ROOT/deploy/report-deployment.sh" <<'EOF'
#!/bin/bash
# Report deployment to Matrix channel

cd "$(dirname "$0")/.."
source venv/bin/activate
export MATRIX_BOT_PASSWORD="${MATRIX_BOT_PASSWORD:-llm-tutor-2024}"
python3 deploy/matrix-agent.py report
EOF

chmod +x "$PROJECT_ROOT/deploy/report-deployment.sh"

# Update deploy.sh to report after successful deployment
if ! grep -q "report-deployment.sh" "$PROJECT_ROOT/deploy/deploy.sh"; then
    echo "Adding Matrix reporting to deployment script..."
    cat >> "$PROJECT_ROOT/deploy/deploy.sh" <<'EOF'

# Report deployment to Matrix
echo "Reporting deployment to Matrix..."
./deploy/report-deployment.sh || echo "Matrix report failed (non-critical)"
EOF
fi

# Enable and start listener service
echo "Enabling Matrix listener service..."
sudo systemctl daemon-reload
sudo systemctl enable matrix-listener
sudo systemctl start matrix-listener

echo ""
echo "=================================================="
echo "Matrix agent configured successfully!"
echo "=================================================="
echo ""
echo "Services:"
echo "  • Matrix listener: sudo systemctl status matrix-listener"
echo ""
echo "The agent will:"
echo "  • Listen for user feedback in #agentic-sdlc:themultiverse.school"
echo "  • Report deployments (max once per day)"
echo "  • Block malicious commands with prompt defenses"
echo ""
echo "Feedback is saved to: feedback/matrix-feedback.jsonl"
echo ""
