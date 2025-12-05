#!/bin/bash
# Deploy CodeMentor backend to Compute Engine VM
# This script can be run manually or from CI/CD

set -e

# Load configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/../configs/project.env"

VM_NAME="codementor-app-vm"
APP_DIR="/opt/codementor"
BACKEND_DIR="${SCRIPT_DIR}/../../../.."

echo "╔═══════════════════════════════════════════════════════════╗"
echo "║   Deploying CodeMentor to VM                               ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo ""

# Check if VM exists
if ! gcloud compute instances describe "${VM_NAME}" --zone="${GCP_ZONE}" &>/dev/null; then
    echo "❌ VM ${VM_NAME} does not exist!"
    echo "Run ./07-provision-vm.sh first"
    exit 1
fi

echo "VM found: ${VM_NAME}"
echo ""

# Create deployment package
echo "Creating deployment package..."
cd "${BACKEND_DIR}"

# Create temp directory for deployment
TEMP_DIR=$(mktemp -d)
trap "rm -rf ${TEMP_DIR}" EXIT

# Copy application files
cp -r src "${TEMP_DIR}/"
cp app.py "${TEMP_DIR}/"
cp run.py "${TEMP_DIR}/"
cp requirements.txt "${TEMP_DIR}/"

# Copy alembic if exists
if [ -d "alembic" ]; then
    cp -r alembic "${TEMP_DIR}/"
    cp alembic.ini "${TEMP_DIR}/" 2>/dev/null || true
fi

echo "✓ Deployment package created"

# Upload to VM
echo "Uploading code to VM..."
gcloud compute scp --recurse \
    "${TEMP_DIR}"/* \
    "${VM_NAME}:${APP_DIR}/" \
    --zone="${GCP_ZONE}" \
    --compress

echo "✓ Code uploaded"

# Run deployment commands on VM
echo "Installing dependencies and restarting service..."
gcloud compute ssh "${VM_NAME}" \
    --zone="${GCP_ZONE}" \
    --command="
        set -e
        cd ${APP_DIR}

        # Install/update Python dependencies
        echo 'Installing Python dependencies...'
        python3.11 -m pip install --upgrade pip
        python3.11 -m pip install -r requirements.txt

        # Run database migrations if alembic exists
        if [ -f 'alembic.ini' ]; then
            echo 'Running database migrations...'
            python3.11 -m alembic upgrade head || echo 'No migrations to run'
        fi

        # Restart the service
        echo 'Restarting application service...'
        sudo systemctl restart codementor

        # Wait a bit for service to start
        sleep 3

        # Check service status
        sudo systemctl status codementor --no-pager || true

        echo '✓ Deployment complete!'
    "

# Get VM external IP
EXTERNAL_IP=$(gcloud compute instances describe "${VM_NAME}" \
    --zone="${GCP_ZONE}" \
    --format='get(networkInterfaces[0].accessConfigs[0].natIP)')

echo ""
echo "╔═══════════════════════════════════════════════════════════╗"
echo "║   ✅ Deployment Successful!                                ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo ""
echo "Application URL: http://${EXTERNAL_IP}"
echo "Health Check: http://${EXTERNAL_IP}/health"
echo ""
echo "Useful commands:"
echo "1. View logs:"
echo "   gcloud compute ssh ${VM_NAME} --zone=${GCP_ZONE} --command='sudo journalctl -u codementor -f'"
echo ""
echo "2. Check service status:"
echo "   gcloud compute ssh ${VM_NAME} --zone=${GCP_ZONE} --command='sudo systemctl status codementor'"
echo ""
echo "3. SSH into VM:"
echo "   gcloud compute ssh ${VM_NAME} --zone=${GCP_ZONE}"
echo ""
