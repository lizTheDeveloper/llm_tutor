# Secrets Management Guide

## Overview

This document describes how to manage secrets securely for the CodeMentor application.

## Development Environment

1. **Copy the example file**:
   ```bash
   cp .env.example .env
   ```

2. **Generate strong secrets**:
   ```bash
   # Generate SECRET_KEY
   python3 -c "import secrets; print('SECRET_KEY=' + secrets.token_urlsafe(64))"

   # Generate JWT_SECRET_KEY
   python3 -c "import secrets; print('JWT_SECRET_KEY=' + secrets.token_urlsafe(64))"
   ```

3. **Add API keys**:
   - Get GROQ API key from: https://console.groq.com/keys
   - Get OpenAI API key from: https://platform.openai.com/api-keys
   - Get Anthropic API key from: https://console.anthropic.com/settings/keys
   - Get SendGrid API key from: https://app.sendgrid.com/settings/api_keys
   - Get GitHub OAuth from: https://github.com/settings/developers
   - Get Google OAuth from: https://console.cloud.google.com/apis/credentials

4. **Never commit .env files**:
   - The `.env` file is in `.gitignore` and should NEVER be committed
   - Only `.env.example` should be committed (with placeholder values)

## Production Environment

### Option 1: Environment Variables (Simple)

Set environment variables directly in your hosting platform:
- Heroku: `heroku config:set SECRET_KEY=xxx`
- Railway: Use the Variables tab
- GCP Cloud Run: Use Secret Manager or environment variables
- AWS: Use Systems Manager Parameter Store or Secrets Manager

### Option 2: Secrets Manager (Recommended)

**GCP Secret Manager**:
```bash
# Create secrets
echo -n "your-secret-value" | gcloud secrets create SECRET_KEY --data-file=-

# Access in code (already implemented in deploy/gcp/setup_secrets.sh)
gcloud secrets versions access latest --secret="SECRET_KEY"
```

**AWS Secrets Manager**:
```bash
# Create secret
aws secretsmanager create-secret --name SECRET_KEY --secret-string "your-secret-value"

# Access in code
aws secretsmanager get-secret-value --secret-id SECRET_KEY --query SecretString
```

**HashiCorp Vault** (Self-hosted):
```bash
# Store secret
vault kv put secret/codementor SECRET_KEY="your-secret-value"

# Access secret
vault kv get -field=SECRET_KEY secret/codementor
```

## Secret Rotation

**Required Rotation Schedule**:
- `SECRET_KEY`: Every 90 days
- `JWT_SECRET_KEY`: Every 90 days
- OAuth secrets: When provider requires or annually
- API keys: When provider requires or annually

**Rotation Process**:
1. Generate new secret value
2. Update in secrets manager
3. Deploy new version of application
4. Verify application works with new secret
5. Old secret can be deleted after 24 hours (to allow for rollback)

**JWT Secret Rotation** (Special Handling):
- JWT tokens signed with old key will become invalid
- Options:
  - Dual-key support: Accept both old and new keys for 24 hours
  - Force re-login: Invalidate all sessions, users must re-authenticate
  - Recommended: Implement dual-key support to avoid mass logout

## Security Checklist

- [ ] All secrets are at least 64 characters (for SECRET_KEY and JWT_SECRET_KEY)
- [ ] No secrets committed to git repository
- [ ] `.env` files are in `.gitignore`
- [ ] Production secrets stored in secrets manager (not environment variables)
- [ ] Secrets rotation schedule documented and calendar reminders set
- [ ] Team members know how to access secrets securely
- [ ] Secrets are not logged or exposed in error messages
- [ ] API keys have minimum required permissions (principle of least privilege)

## Auditing for Leaked Secrets

**Check git history**:
```bash
# Search for potential secrets in git history
git log -p --all | grep -i "secret_key\|api_key\|password" | head -100

# Use git-secrets tool (recommended)
git secrets --scan-history
```

**If secrets found in git history**:
1. **IMMEDIATELY** rotate all affected secrets
2. Consider using BFG Repo-Cleaner to remove from history:
   ```bash
   bfg --replace-text passwords.txt
   git reflog expire --expire=now --all && git gc --prune=now --aggressive
   git push --force
   ```
3. Notify security team
4. Review access logs for unauthorized usage

## Emergency Response

**If a secret is leaked**:
1. **IMMEDIATELY** rotate the leaked secret
2. Review logs for unauthorized access
3. Notify security team and stakeholders
4. Update incident response documentation
5. Conduct post-mortem to prevent future leaks

## References

- [OWASP Secrets Management Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html)
- [NIST SP 800-57: Key Management](https://csrc.nist.gov/publications/detail/sp/800-57-part-1/rev-5/final)
