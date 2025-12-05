# GCP VM Deployment Guide

**Cost-Effective Alternative to Cloud Run**

This guide covers deploying CodeMentor to a single GCP Compute Engine VM for ~$7-14/month instead of Cloud Run's serverless pricing.

## Cost Comparison

| Option | Monthly Cost | Specs |
|--------|--------------|-------|
| **e2-micro** (Free tier) | ~$7/month | 2 vCPUs, 1 GB RAM |
| **e2-small** (Recommended) | ~$14/month | 2 vCPUs, 2 GB RAM |
| **e2-medium** | ~$27/month | 2 vCPUs, 4 GB RAM |
| Cloud Run | Variable | Pay per request + always-on costs |

## Architecture

```
Internet → Nginx (Port 80) → Python App (Port 5000) → PostgreSQL/Redis
```

- **Nginx**: Reverse proxy handling HTTP traffic
- **Python App**: Quart backend running as systemd service
- **PostgreSQL**: Cloud SQL (shared with Cloud Run setup)
- **Redis**: Memorystore (shared with Cloud Run setup)

## Prerequisites

1. **GCP Account** with billing enabled
2. **gcloud CLI** installed and authenticated
3. **Existing Infrastructure** from Stage 1:
   - VPC Network (A1)
   - Cloud SQL PostgreSQL (A1)
   - Memorystore Redis (A1)

If you haven't run the infrastructure setup:
```bash
cd backend/src/infrastructure/gcp/scripts
./00-setup-project.sh
./01-setup-network.sh
./02-provision-database.sh
./03-provision-redis.sh
```

## Initial Setup

### 1. Configure Project Settings

Edit `backend/src/infrastructure/gcp/configs/project.env`:

```bash
export PROJECT_ID="your-project-id"
export GCP_REGION="us-central1"
export GCP_ZONE="us-central1-a"
```

### 2. Provision the VM

```bash
cd backend/src/infrastructure/gcp/scripts
chmod +x 07-provision-vm.sh
./07-provision-vm.sh
```

This creates:
- e2-small VM instance (change to `e2-micro` in script for free tier)
- 20GB standard persistent disk
- Firewall rules for HTTP/HTTPS
- Nginx reverse proxy configuration
- systemd service for the application

**Initial setup takes ~5 minutes**

### 3. Deploy the Application

```bash
chmod +x deploy-to-vm.sh
./deploy-to-vm.sh
```

This will:
- Package the backend code
- Upload to the VM via `gcloud compute scp`
- Install Python dependencies
- Run database migrations
- Restart the application service

### 4. Verify Deployment

Get the VM's IP address:
```bash
gcloud compute instances describe codementor-app-vm \
  --zone=us-central1-a \
  --format='get(networkInterfaces[0].accessConfigs[0].natIP)'
```

Test the application:
```bash
curl http://YOUR_VM_IP/health
```

## Automatic Deployment (GitHub Actions)

### Setup GitHub Secrets

1. **Create a GCP Service Account** with permissions:
   - Compute Instance Admin
   - Service Account User
   - Secret Manager Secret Accessor

```bash
# Create service account
gcloud iam service-accounts create github-deployer \
  --display-name="GitHub Actions Deployer"

# Grant permissions
PROJECT_ID=$(gcloud config get-value project)
SA_EMAIL="github-deployer@${PROJECT_ID}.iam.gserviceaccount.com"

gcloud projects add-iam-policy-binding ${PROJECT_ID} \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/compute.instanceAdmin.v1"

gcloud projects add-iam-policy-binding ${PROJECT_ID} \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/iam.serviceAccountUser"

gcloud projects add-iam-policy-binding ${PROJECT_ID} \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/secretmanager.secretAccessor"

# Create and download key
gcloud iam service-accounts keys create ~/gcp-key.json \
  --iam-account="${SA_EMAIL}"
```

2. **Add GitHub Secrets** (Settings → Secrets and variables → Actions):
   - `GCP_SA_KEY`: Contents of `~/gcp-key.json`
   - `GCP_PROJECT_ID`: Your GCP project ID

3. **Push to main** - Deployment happens automatically!

The workflow (`.github/workflows/deploy-to-vm.yml`) triggers on:
- Push to `main` branch with changes to `backend/**`
- Manual workflow dispatch

## Managing the VM

### SSH into the VM
```bash
gcloud compute ssh codementor-app-vm --zone=us-central1-a
```

### View Application Logs
```bash
# Real-time logs
gcloud compute ssh codementor-app-vm --zone=us-central1-a \
  --command='sudo journalctl -u codementor -f'

# Last 100 lines
gcloud compute ssh codementor-app-vm --zone=us-central1-a \
  --command='sudo journalctl -u codementor -n 100'
```

### Check Service Status
```bash
gcloud compute ssh codementor-app-vm --zone=us-central1-a \
  --command='sudo systemctl status codementor'
```

### Restart the Application
```bash
gcloud compute ssh codementor-app-vm --zone=us-central1-a \
  --command='sudo systemctl restart codementor'
```

### View Nginx Logs
```bash
gcloud compute ssh codementor-app-vm --zone=us-central1-a \
  --command='sudo tail -f /var/log/nginx/access.log'
```

## Environment Variables & Secrets

The VM fetches secrets from GCP Secret Manager during startup:
- `database-url`: PostgreSQL connection string
- `redis-url`: Redis connection string
- `jwt-secret`: JWT signing key
- `groq-api-key`: GROQ LLM API key

To update secrets:
```bash
# Create or update a secret
echo -n "your-secret-value" | gcloud secrets create secret-name \
  --data-file=- \
  --replication-policy="automatic"

# Or update existing
echo -n "new-value" | gcloud secrets versions add secret-name \
  --data-file=-
```

After updating secrets, restart the VM or the service:
```bash
# Just restart service (secrets loaded from /opt/codementor/.env)
gcloud compute ssh codementor-app-vm --zone=us-central1-a \
  --command='sudo systemctl restart codementor'

# Or reboot VM (runs startup script again)
gcloud compute instances stop codementor-app-vm --zone=us-central1-a
gcloud compute instances start codementor-app-vm --zone=us-central1-a
```

## Monitoring & Maintenance

### Check Disk Usage
```bash
gcloud compute ssh codementor-app-vm --zone=us-central1-a \
  --command='df -h'
```

### Check Memory Usage
```bash
gcloud compute ssh codementor-app-vm --zone=us-central1-a \
  --command='free -h'
```

### Update System Packages
```bash
gcloud compute ssh codementor-app-vm --zone=us-central1-a \
  --command='sudo apt-get update && sudo apt-get upgrade -y'
```

## Scaling Options

### Vertical Scaling (More Resources)
```bash
# Stop VM
gcloud compute instances stop codementor-app-vm --zone=us-central1-a

# Change machine type
gcloud compute instances set-machine-type codementor-app-vm \
  --zone=us-central1-a \
  --machine-type=e2-medium

# Start VM
gcloud compute instances start codementor-app-vm --zone=us-central1-a
```

### Horizontal Scaling (Load Balancer + Multiple VMs)
For high traffic, consider:
1. Create VM instance template from current setup
2. Create managed instance group
3. Add HTTP(S) load balancer
4. Enable autoscaling based on CPU/requests

See Cloud Run for easier horizontal scaling.

## Cost Optimization Tips

1. **Use e2-micro for dev/staging** (~$7/month, free tier eligible)
2. **Use Preemptible/Spot VMs** for non-production (~70% cheaper)
3. **Stop VM when not in use** (only pay for disk storage)
4. **Use smaller disk** if you don't need 20GB
5. **Set up budget alerts** in GCP Console

## Troubleshooting

### Service Won't Start
```bash
# Check logs for errors
gcloud compute ssh codementor-app-vm --zone=us-central1-a \
  --command='sudo journalctl -u codementor -n 50'

# Check if port 5000 is in use
gcloud compute ssh codementor-app-vm --zone=us-central1-a \
  --command='sudo lsof -i :5000'
```

### Can't Connect to Database
```bash
# Test database connection
gcloud compute ssh codementor-app-vm --zone=us-central1-a \
  --command='cat /opt/codementor/.env | grep DATABASE_URL'

# Check if VM can reach Cloud SQL
gcloud compute ssh codementor-app-vm --zone=us-central1-a \
  --command='nc -zv YOUR_DB_IP 5432'
```

### 502 Bad Gateway (Nginx)
```bash
# Check if application is running
gcloud compute ssh codementor-app-vm --zone=us-central1-a \
  --command='sudo systemctl status codementor'

# Check nginx config
gcloud compute ssh codementor-app-vm --zone=us-central1-a \
  --command='sudo nginx -t'
```

## Deleting the VM

To remove everything and stop charges:
```bash
gcloud compute instances delete codementor-app-vm \
  --zone=us-central1-a \
  --quiet
```

The database and Redis instances will remain (charged separately).

## Next Steps

1. **Set up monitoring**: Enable Cloud Monitoring for the VM
2. **Configure alerts**: CPU, memory, disk usage alerts
3. **Enable HTTPS**: Use Certbot for Let's Encrypt SSL certificate
4. **Set up backups**: Snapshot schedule for the VM disk
5. **Configure logging**: Send application logs to Cloud Logging

## Support

- GCP Compute Engine Docs: https://cloud.google.com/compute/docs
- Nginx Configuration: https://nginx.org/en/docs/
- systemd Services: `man systemd.service`
