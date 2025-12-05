#!/bin/bash
# Provision a cost-effective Compute Engine VM for CodeMentor
# Uses e2-small (~$14/month) or e2-micro (free tier, ~$7/month)

set -e

# Load configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/../configs/project.env"

# VM Configuration
VM_NAME="codementor-app-vm"
MACHINE_TYPE="e2-small"  # Change to e2-micro for free tier
BOOT_DISK_SIZE="20GB"
BOOT_DISK_TYPE="pd-standard"  # pd-standard is cheaper than pd-ssd
VM_TAGS="http-server,https-server,codementor-app"

echo "=== Provisioning Compute Engine VM ==="
echo ""
echo "Configuration:"
echo "  VM Name: ${VM_NAME}"
echo "  Machine Type: ${MACHINE_TYPE}"
echo "  Zone: ${GCP_ZONE}"
echo "  Disk Size: ${BOOT_DISK_SIZE}"
echo ""

# Check if VM already exists
if gcloud compute instances describe "${VM_NAME}" --zone="${GCP_ZONE}" 2>/dev/null; then
    echo "⚠️  VM ${VM_NAME} already exists"
    read -p "Delete and recreate? (y/N) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "Deleting existing VM..."
        gcloud compute instances delete "${VM_NAME}" --zone="${GCP_ZONE}" --quiet
    else
        echo "Keeping existing VM"
        exit 0
    fi
fi

# Create startup script (will be created separately)
STARTUP_SCRIPT="${SCRIPT_DIR}/vm-startup.sh"

# Create VM instance
echo "Creating VM instance..."
gcloud compute instances create "${VM_NAME}" \
    --project="${PROJECT_ID}" \
    --zone="${GCP_ZONE}" \
    --machine-type="${MACHINE_TYPE}" \
    --network-interface="network=${VPC_NETWORK_NAME},subnet=${SUBNET_NAME},network-tier=STANDARD" \
    --maintenance-policy=MIGRATE \
    --provisioning-model=STANDARD \
    --scopes=https://www.googleapis.com/auth/cloud-platform \
    --tags="${VM_TAGS}" \
    --create-disk="auto-delete=yes,boot=yes,device-name=${VM_NAME},image=projects/ubuntu-os-cloud/global/images/family/ubuntu-2204-lts,mode=rw,size=${BOOT_DISK_SIZE},type=${BOOT_DISK_TYPE}" \
    --metadata-from-file=startup-script="${STARTUP_SCRIPT}" \
    --shielded-secure-boot \
    --shielded-vtpm \
    --shielded-integrity-monitoring \
    --reservation-affinity=any

echo "✓ VM instance created"

# Create firewall rule for HTTP/HTTPS
echo "Creating firewall rules..."
gcloud compute firewall-rules create "${VM_NAME}-allow-http" \
    --project="${PROJECT_ID}" \
    --network="${VPC_NETWORK_NAME}" \
    --allow=tcp:80,tcp:443,tcp:5000 \
    --source-ranges=0.0.0.0/0 \
    --target-tags="${VM_TAGS}" \
    --description="Allow HTTP/HTTPS traffic to CodeMentor VM" \
    2>/dev/null || echo "Firewall rule already exists"

echo "✓ Firewall rules configured"

# Get VM external IP
EXTERNAL_IP=$(gcloud compute instances describe "${VM_NAME}" \
    --zone="${GCP_ZONE}" \
    --format='get(networkInterfaces[0].accessConfigs[0].natIP)')

echo ""
echo "╔═══════════════════════════════════════════════════════════╗"
echo "║   ✅ VM Provisioned Successfully!                         ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo ""
echo "VM Details:"
echo "  Name: ${VM_NAME}"
echo "  Zone: ${GCP_ZONE}"
echo "  External IP: ${EXTERNAL_IP}"
echo "  Machine Type: ${MACHINE_TYPE}"
echo ""
echo "Estimated Monthly Cost:"
echo "  e2-micro: ~\$7/month (free tier eligible)"
echo "  e2-small: ~\$14/month"
echo ""
echo "Next steps:"
echo "1. SSH into VM:"
echo "   gcloud compute ssh ${VM_NAME} --zone=${GCP_ZONE}"
echo ""
echo "2. Check startup script logs:"
echo "   gcloud compute ssh ${VM_NAME} --zone=${GCP_ZONE} --command='sudo journalctl -u google-startup-scripts.service'"
echo ""
echo "3. Access application:"
echo "   http://${EXTERNAL_IP}:5000"
echo ""
