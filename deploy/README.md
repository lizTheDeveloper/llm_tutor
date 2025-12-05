# Autonomous Development System - GCP Deployment

This directory contains scripts to deploy the autonomous development system to Google Cloud Platform.

## Architecture

**VM Specification:**
- **Instance Type**: e2-small (2 vCPUs, 2GB RAM) - upgrade to e2-medium for better performance
- **OS**: Ubuntu 22.04 LTS
- **Disk**: 30GB SSD
- **Cost**: ~$12-15/month for e2-small, ~$24-27/month for e2-medium

**Autonomous Agents:**
1. **TDD Agent** - Runs every 30 minutes, completes work streams from roadmap
2. **Reviewer Agent** - Runs every hour, performs architectural reviews
3. **Summary Agent** - Runs every 4 hours, emails development summaries

## Prerequisites

1. **Google Cloud Project**
   ```bash
   export GCP_PROJECT_ID="your-project-id"
   export GCP_ZONE="us-central1-a"  # or your preferred zone
   ```

2. **gcloud CLI** installed and authenticated
   ```bash
   gcloud auth login
   gcloud config set project $GCP_PROJECT_ID
   ```

3. **Enable required APIs**
   ```bash
   gcloud services enable compute.googleapis.com
   ```

## Deployment Steps

### 1. Create the VM

```bash
cd deploy
./create-gcp-vm.sh
```

This will:
- Create an e2-small VM instance
- Run the bootstrap script to install all dependencies
- Set up PostgreSQL, Redis, and other services
- Configure cron jobs for all three agents

### 2. Wait for Bootstrap

The bootstrap script takes ~3-5 minutes. Monitor progress:

```bash
gcloud compute ssh llm-tutor-autonomous-dev --zone=$GCP_ZONE
tail -f /var/log/bootstrap.log
```

### 3. Configure Secrets

Once bootstrap completes:

```bash
# On the VM
cd ~/llm_tutor
./deploy/configure-secrets.sh
```

This will prompt you to configure:
- Email address for summaries
- OpenAI API key
- Database password
- Other secrets

### 4. Authenticate Claude CLI

```bash
# On the VM
claude setup-token
```

Follow the prompts to authenticate with your Claude account.

### 5. Set Up Git Authentication

For automatic git push (optional):

```bash
# Generate SSH key
ssh-keygen -t ed25519 -C "autonomous@llmtutor.dev"

# Display public key
cat ~/.ssh/id_ed25519.pub

# Add the key to GitHub: Settings > SSH Keys

# Test connection
ssh -T git@github.com
```

### 6. Test Agents Manually

Before relying on cron, test each agent:

```bash
cd ~/llm_tutor

# Test TDD agent
./autonomous-agent.sh

# Test reviewer
./autonomous-reviewer.sh

# Test summary
./autonomous-summary.sh
```

### 7. Monitor Operations

```bash
# Watch cron logs
tail -f agent-logs/cron-*.log

# Check crontab
crontab -l

# View summaries
ls -la summaries/

# Check email sending
tail -f /var/log/mail.log
```

## Cron Schedule

```
*/30 * * * *   # TDD Agent - every 30 minutes
0 * * * *      # Reviewer - every hour at :00
0 */4 * * *    # Summary - every 4 hours (00:00, 04:00, 08:00, etc.)
```

## Email Configuration

The system uses Postfix for sending emails. Configure your email:

1. Edit `/etc/postfix/main.cf` for custom SMTP settings
2. Or use the default local mail delivery
3. Test email: `echo "test" | mail -s "Test" your-email@example.com`

For production, consider using:
- SendGrid
- Mailgun
- Amazon SES
- Gmail SMTP relay

## Monitoring & Maintenance

**Check VM Status:**
```bash
gcloud compute instances describe llm-tutor-autonomous-dev --zone=$GCP_ZONE
```

**SSH into VM:**
```bash
gcloud compute ssh llm-tutor-autonomous-dev --zone=$GCP_ZONE
```

**View Logs:**
```bash
# All agent logs
ls -lah ~/llm_tutor/agent-logs/

# Cron logs
tail -f ~/llm_tutor/agent-logs/cron-*.log

# System logs
tail -f /var/log/syslog
```

**Check Disk Usage:**
```bash
df -h
du -sh ~/llm_tutor/
```

**Update Code:**
```bash
cd ~/llm_tutor
git pull
```

## Stopping the System

**Temporarily stop agents:**
```bash
crontab -e
# Comment out the cron jobs with #
```

**Delete the VM:**
```bash
gcloud compute instances delete llm-tutor-autonomous-dev --zone=$GCP_ZONE
```

## Scaling Up

If e2-small is too slow, upgrade to e2-medium:

```bash
# Stop VM
gcloud compute instances stop llm-tutor-autonomous-dev --zone=$GCP_ZONE

# Change machine type
gcloud compute instances set-machine-type llm-tutor-autonomous-dev \
  --machine-type=e2-medium \
  --zone=$GCP_ZONE

# Start VM
gcloud compute instances start llm-tutor-autonomous-dev --zone=$GCP_ZONE
```

## Cost Optimization

**e2-small (2GB RAM)**: ~$12-15/month
- Good for: Low to moderate activity
- May struggle with: Large codebases, multiple concurrent agents

**e2-medium (4GB RAM)**: ~$24-27/month
- Good for: Steady development activity
- Recommended for production use

**Further optimization:**
- Use preemptible instances (60-91% cheaper, can be interrupted)
- Schedule VM to stop during off-hours
- Use committed use discounts for 1-3 year terms

## Troubleshooting

**Agents not running:**
```bash
# Check cron
crontab -l
tail -f /var/log/syslog | grep CRON

# Check permissions
ls -la ~/llm_tutor/*.sh
```

**Email not sending:**
```bash
# Check postfix
systemctl status postfix
tail -f /var/log/mail.log

# Test mail
echo "test" | mail -s "Test" your-email@example.com
```

**Claude CLI issues:**
```bash
# Re-authenticate
claude setup-token

# Check Claude installation
which claude
claude --version
```

**Database issues:**
```bash
# Check PostgreSQL
sudo systemctl status postgresql
sudo -u postgres psql -l
```

## Security Notes

1. **Firewall**: The VM has basic firewall rules. Adjust as needed.
2. **SSH Keys**: Use SSH keys instead of passwords
3. **Secrets**: Never commit .env file or secrets to git
4. **Updates**: Regularly update system packages
5. **Monitoring**: Set up Cloud Monitoring for alerts

## Support

For issues or questions:
1. Check logs: `agent-logs/` and `/var/log/`
2. Review bootstrap log: `/var/log/bootstrap.log`
3. Test agents manually to isolate issues
4. Check VM resources: `htop`, `df -h`
