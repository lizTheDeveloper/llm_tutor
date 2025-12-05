# Quick Start - Deploy Autonomous Development to GCP

## One-Command Deployment

```bash
# 1. Set your GCP project
export GCP_PROJECT_ID="your-project-id"
export GCP_ZONE="us-central1-a"

# 2. Create the VM
cd deploy
./create-gcp-vm.sh

# 3. Wait 3-5 minutes, then SSH in
gcloud compute ssh llm-tutor-autonomous-dev --zone=$GCP_ZONE

# 4. Configure secrets
cd ~/llm_tutor
./deploy/configure-secrets.sh

# 5. Authenticate Claude
claude setup-token

# 6. Done! Agents will start automatically via cron
```

## What Gets Deployed

**Autonomous Agents (Running on e2-small VM):**
- 🔧 **TDD Agent**: Every 30 min - Builds features from roadmap
- 🔍 **Reviewer**: Every hour - Performs architectural reviews
- 📧 **Summary**: Every 4 hours - Emails progress reports

**Cost:** ~$12-15/month (e2-small) or ~$24-27/month (e2-medium)

## First Summary Email

You'll receive your first summary email within 4 hours of deployment at:
- 00:00, 04:00, 08:00, 12:00, 16:00, 20:00 (server time)

## Monitor Progress

```bash
# SSH into VM
gcloud compute ssh llm-tutor-autonomous-dev --zone=$GCP_ZONE

# Watch agent activity
tail -f ~/llm_tutor/agent-logs/cron-*.log

# View summaries
cat ~/llm_tutor/summaries/summary-*.txt

# Check what's been built
cd ~/llm_tutor && git log --oneline
```

## Stop Everything

```bash
# Delete VM (stops all costs)
gcloud compute instances delete llm-tutor-autonomous-dev --zone=$GCP_ZONE
```

## Troubleshooting

**Email not arriving?**
```bash
# Check if email was sent
tail -f /var/log/mail.log

# Test email
echo "test" | mail -s "Test" your-email@example.com
```

**Agents not running?**
```bash
# Check cron
crontab -l
tail -f /var/log/syslog | grep CRON
```

**Need more power?**
Upgrade to e2-medium:
```bash
gcloud compute instances stop llm-tutor-autonomous-dev --zone=$GCP_ZONE
gcloud compute instances set-machine-type llm-tutor-autonomous-dev --machine-type=e2-medium --zone=$GCP_ZONE
gcloud compute instances start llm-tutor-autonomous-dev --zone=$GCP_ZONE
```

For detailed instructions, see [README.md](README.md)
