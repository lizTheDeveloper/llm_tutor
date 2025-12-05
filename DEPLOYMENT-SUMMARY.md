# CodeMentor - VM Deployment Setup Complete ✅

## What's Been Created

You now have a **cost-effective VM deployment system** that deploys to a GCP Compute Engine VM (~$7-14/month) instead of expensive Cloud Run.

### New Files Created:

1. **Provisioning Script**: `backend/src/infrastructure/gcp/scripts/07-provision-vm.sh`
   - Creates e2-small VM (~$14/month) or e2-micro (~$7/month, free tier)
   - Sets up networking and firewall rules
   - Configures VM for application hosting

2. **Startup Script**: `backend/src/infrastructure/gcp/scripts/vm-startup.sh`
   - Runs when VM boots
   - Installs Docker, Python, Nginx
   - Creates systemd service for your app
   - Fetches secrets from Secret Manager

3. **Deployment Script**: `backend/src/infrastructure/gcp/scripts/deploy-to-vm.sh`
   - Uploads code to VM
   - Installs dependencies
   - Runs migrations
   - Restarts service

4. **GitHub Actions Workflow**: `.github/workflows/deploy-to-vm.yml`
   - **Auto-deploys when you push to main!** 🚀
   - Runs tests
   - Uploads code to VM
   - Restarts application

5. **Documentation**: `backend/src/infrastructure/gcp/VM-DEPLOYMENT.md`
   - Complete setup guide
   - Troubleshooting tips
   - Cost optimization strategies

## Quick Start

### 1. Set Up Infrastructure (One-Time)

```bash
cd backend/src/infrastructure/gcp/scripts

# Configure your project ID in configs/project.env first!
nano ../configs/project.env

# Run infrastructure setup (if not done already)
./00-setup-project.sh
./01-setup-network.sh
./02-provision-database.sh  # Cloud SQL
./03-provision-redis.sh     # Memorystore

# Create the VM
./07-provision-vm.sh
```

**Cost Tip**: Edit `07-provision-vm.sh` and change `MACHINE_TYPE="e2-small"` to `MACHINE_TYPE="e2-micro"` for free tier (~$7/month instead of ~$14/month).

### 2. Manual Deployment

```bash
cd backend/src/infrastructure/gcp/scripts
./deploy-to-vm.sh
```

This will:
- Package your backend code
- Upload to the VM
- Install dependencies
- Restart the service

### 3. Set Up Auto-Deploy on Push to Main (GitHub Actions)

#### a. Create GCP Service Account

```bash
# Create service account for GitHub
gcloud iam service-accounts create github-deployer \
  --display-name="GitHub Actions Deployer"

# Get your project ID
PROJECT_ID=$(gcloud config get-value project)
SA_EMAIL="github-deployer@${PROJECT_ID}.iam.gserviceaccount.com"

# Grant permissions
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

#### b. Add GitHub Secrets

Go to your GitHub repo: Settings → Secrets and variables → Actions

Add these secrets:
- **`GCP_SA_KEY`**: Paste the entire contents of `~/gcp-key.json`
- **`GCP_PROJECT_ID`**: Your GCP project ID (run `gcloud config get-value project`)

#### c. Push to Main = Auto Deploy! 🎉

Now whenever you merge to `main`, GitHub Actions will:
1. Run tests
2. Upload code to your VM
3. Install dependencies
4. Run migrations
5. Restart the app

## Getting Your App URL

```bash
# Get VM IP address
gcloud compute instances describe codementor-app-vm \
  --zone=us-central1-a \
  --format='get(networkInterfaces[0].accessConfigs[0].natIP)'

# Test health check
curl http://YOUR_VM_IP/health
```

## Cost Breakdown

| Component | Monthly Cost |
|-----------|--------------|
| VM (e2-micro) | ~$7 (free tier eligible) |
| VM (e2-small) | ~$14 |
| Cloud SQL (db-f1-micro) | ~$7 |
| Memorystore Redis (1GB) | ~$35 |
| **Total** | **~$49-56/month** |

**vs Cloud Run**: Variable, but typically $50-200+/month for always-on services

### Further Cost Optimization:

1. **Use local Redis instead of Memorystore**: Save ~$35/month
   - Install Redis on the VM itself
   - Edit `vm-startup.sh` to install Redis

2. **Use e2-micro instead of e2-small**: Save ~$7/month
   - Good for dev/staging
   - May be slower under load

3. **Stop VM when not in use**: Only pay for disk (~$2/month)
   ```bash
   gcloud compute instances stop codementor-app-vm --zone=us-central1-a
   ```

## Monitoring & Management

### View Logs
```bash
gcloud compute ssh codementor-app-vm --zone=us-central1-a \
  --command='sudo journalctl -u codementor -f'
```

### Check Service Status
```bash
gcloud compute ssh codementor-app-vm --zone=us-central1-a \
  --command='sudo systemctl status codementor'
```

### SSH Into VM
```bash
gcloud compute ssh codementor-app-vm --zone=us-central1-a
```

### Restart Application
```bash
gcloud compute ssh codementor-app-vm --zone=us-central1-a \
  --command='sudo systemctl restart codementor'
```

## What Happens When You Push to Main?

1. GitHub Actions workflow triggers
2. Code is tested (if you have tests)
3. Code is packaged
4. Uploaded to VM via `gcloud compute scp`
5. Dependencies installed
6. Database migrations run
7. Application service restarted
8. Health check performed
9. ✅ Deployment complete!

**Total time**: ~2-3 minutes

## Next Steps

- [ ] Configure `backend/src/infrastructure/gcp/configs/project.env` with your GCP project
- [ ] Run infrastructure setup scripts
- [ ] Create VM with `07-provision-vm.sh`
- [ ] Test manual deployment with `deploy-to-vm.sh`
- [ ] Set up GitHub Actions for auto-deploy
- [ ] Add SSL certificate for HTTPS (optional)
- [ ] Set up monitoring and alerts (optional)

## Need Help?

See the complete guide: `backend/src/infrastructure/gcp/VM-DEPLOYMENT.md`
