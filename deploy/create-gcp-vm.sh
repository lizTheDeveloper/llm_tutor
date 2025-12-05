#!/bin/bash

# Create GCP VM for Autonomous Development System
# This script creates an E2-small VM and sets up the autonomous agents

set -e

# Configuration
PROJECT_ID="${GCP_PROJECT_ID:-your-project-id}"
ZONE="${GCP_ZONE:-europe-north1-a}"  # Finland - 100% carbon-free (hydroelectric + wind)
VM_NAME="llm-tutor-autonomous-dev"
MACHINE_TYPE="e2-small"  # 2 vCPUs, 2GB RAM - upgrade to e2-medium (4GB RAM) if needed
DISK_SIZE="30GB"
IMAGE_FAMILY="ubuntu-2204-lts"
IMAGE_PROJECT="ubuntu-os-cloud"

echo "=================================================="
echo "Creating Autonomous Development VM"
echo "=================================================="
echo "Project: $PROJECT_ID"
echo "Zone: $ZONE"
echo "Machine Type: $MACHINE_TYPE"
echo "VM Name: $VM_NAME"
echo ""

# Check if VM already exists
if gcloud compute instances describe "$VM_NAME" --project="$PROJECT_ID" --zone="$ZONE" &>/dev/null; then
    echo "VM $VM_NAME already exists."
    read -p "Delete and recreate? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "Deleting existing VM..."
        gcloud compute instances delete "$VM_NAME" --project="$PROJECT_ID" --zone="$ZONE" --quiet
    else
        echo "Exiting."
        exit 1
    fi
fi

# Create the VM
echo "Creating VM instance..."
gcloud compute instances create "$VM_NAME" \
    --project="$PROJECT_ID" \
    --zone="$ZONE" \
    --machine-type="$MACHINE_TYPE" \
    --boot-disk-size="$DISK_SIZE" \
    --image-family="$IMAGE_FAMILY" \
    --image-project="$IMAGE_PROJECT" \
    --metadata-from-file=startup-script=deploy/vm-bootstrap.sh \
    --scopes=cloud-platform \
    --tags=http-server,https-server

echo ""
echo "✓ VM created successfully!"
echo ""
echo "VM Details:"
gcloud compute instances describe "$VM_NAME" --project="$PROJECT_ID" --zone="$ZONE" --format="table(name,status,networkInterfaces[0].accessConfigs[0].natIP)"

echo ""
echo "Next steps:"
echo "1. Wait ~3-5 minutes for bootstrap script to complete"
echo "2. SSH into VM: gcloud compute ssh $VM_NAME --project=$PROJECT_ID --zone=$ZONE"
echo "3. Check bootstrap progress: tail -f /var/log/bootstrap.log"
echo "4. Configure secrets: cd ~/llm_tutor && ./deploy/configure-secrets.sh"
echo "5. Start agents: sudo systemctl start autonomous-agents"
