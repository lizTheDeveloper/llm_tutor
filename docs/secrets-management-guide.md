# Secrets Management Guide
# CodeMentor Platform

**Version:** 1.0
**Date:** 2025-12-06
**Work Stream:** SEC-2 (Secrets Management)

---

## Table of Contents
1. [Overview](#overview)
2. [Security Requirements](#security-requirements)
3. [Development Setup](#development-setup)
4. [Production Deployment](#production-deployment)
5. [Secret Rotation](#secret-rotation)
6. [Troubleshooting](#troubleshooting)

---

## Overview

This guide describes how secrets (API keys, passwords, tokens) are managed in the CodeMentor platform. Proper secrets management is critical for security.

### Critical Security Rules

**NEVER:**
- ❌ Commit `.env` files to git
- ❌ Share production secrets in Slack/email
- ❌ Use weak or development secrets in production
- ❌ Store secrets in code comments or documentation
- ❌ Reuse secrets across environments

**ALWAYS:**
- ✅ Use `.env.example` as a template
- ✅ Generate strong random secrets (32+ characters)
- ✅ Use different secrets per environment
- ✅ Rotate secrets regularly (quarterly minimum)
- ✅ Use a secrets manager in production

---

## Security Requirements

### Secret Strength Requirements

All secrets MUST meet these criteria:

1. **Minimum Length:** 32 characters
2. **Randomness:** Generated using cryptographically secure random
3. **Uniqueness:** Different secret for each purpose (JWT vs app secret)
4. **No Patterns:** No dictionary words, common patterns, or development defaults

### Prohibited Secrets

The following secrets will be REJECTED in production:

- Containing: `changeme`, `password`, `secret`, `test`, `development`, `default`
- Less than 32 characters
- Any secret found in `.env.example`

---

## Development Setup

### 1. Initial Setup

```bash
# 1. Copy the example file
cp .env.example .env

# 2. Generate strong secrets
python -c 'import secrets; print("SECRET_KEY=" + secrets.token_urlsafe(32))'
python -c 'import secrets; print("JWT_SECRET_KEY=" + secrets.token_urlsafe(32))'

# 3. Edit .env with your generated secrets and local configuration
nano .env
```

### 2. Required Environment Variables (Development)

```bash
# Application
SECRET_KEY=<generated-32+-char-secret>
JWT_SECRET_KEY=<generated-32+-char-secret>
APP_ENV=development

# Database (local PostgreSQL)
DATABASE_URL=postgresql://username:password@localhost:5432/llm_tutor_dev

# Redis (local)
REDIS_URL=redis://localhost:6379/0

# URLs (development allows HTTP)
FRONTEND_URL=http://localhost:3000
BACKEND_URL=http://localhost:5000

# LLM API (optional in development)
GROQ_API_KEY=<your-groq-api-key-if-testing-llm>
```

### 3. Verify Configuration

```bash
# Check that .env is NOT tracked in git
git ls-files .env
# Should return nothing

# Verify configuration loads correctly
cd backend
python -c "from src.config import settings; print('Config loaded successfully!')"
```

---

## Production Deployment

### Option 1: Environment Variables (Recommended for Cloud Deployment)

#### AWS ECS/EC2

```bash
# Set environment variables in task definition or EC2 user data
export SECRET_KEY=<production-secret>
export JWT_SECRET_KEY=<production-jwt-secret>
export APP_ENV=production
export DATABASE_URL=<rds-postgresql-url>
export REDIS_URL=<elasticache-redis-url>
export FRONTEND_URL=https://app.codementor.io
export BACKEND_URL=https://api.codementor.io
export GROQ_API_KEY=<production-groq-key>
```

#### Docker/Kubernetes

```yaml
# kubernetes-secret.yaml
apiVersion: v1
kind: Secret
metadata:
  name: codementor-secrets
type: Opaque
stringData:
  SECRET_KEY: <base64-encoded>
  JWT_SECRET_KEY: <base64-encoded>
  DATABASE_URL: <base64-encoded>
  REDIS_URL: <base64-encoded>
  GROQ_API_KEY: <base64-encoded>
```

### Option 2: AWS Secrets Manager (Best Practice)

#### 1. Store Secrets in AWS Secrets Manager

```bash
# Create secret for CodeMentor production
aws secretsmanager create-secret \
    --name codementor/production/secrets \
    --description "CodeMentor production secrets" \
    --secret-string '{
        "SECRET_KEY": "...",
        "JWT_SECRET_KEY": "...",
        "DATABASE_URL": "...",
        "REDIS_URL": "...",
        "GROQ_API_KEY": "..."
    }'
```

#### 2. Load Secrets in Application (Future Enhancement)

```python
# backend/src/utils/secrets.py
import boto3
import json

def load_secrets_from_aws():
    """Load secrets from AWS Secrets Manager."""
    client = boto3.client('secretsmanager', region_name='us-east-1')

    response = client.get_secret_value(SecretId='codementor/production/secrets')
    secrets = json.loads(response['SecretString'])

    # Set environment variables
    for key, value in secrets.items():
        os.environ[key] = value
```

### Production Configuration Validation

The application will **fail to start** if production configuration is invalid:

✅ **Required Checks (Automatic):**
- SECRET_KEY and JWT_SECRET_KEY ≥ 32 characters
- No development secret patterns detected
- FRONTEND_URL and BACKEND_URL use HTTPS
- DATABASE_URL is valid PostgreSQL connection string
- REDIS_URL is valid Redis connection string
- GROQ_API_KEY set if GROQ is primary LLM provider

**Error Example:**

```
pydantic_core._pydantic_core.ValidationError: 1 validation error for Settings
  Value error, Production secret_key appears to be a development secret!
  Contains 'changeme'. Use a strong random secret:
  python -c 'import secrets; print(secrets.token_urlsafe(32))'
```

---

## Secret Rotation

### When to Rotate Secrets

**Immediate Rotation Required:**
- ⚠️ Secret exposed in code/logs/Slack
- ⚠️ Team member with access leaves
- ⚠️ Security incident or breach suspected
- ⚠️ Secret older than 90 days (policy)

**Recommended Schedule:**
- 🔄 Quarterly rotation (every 90 days)
- 🔄 After major infrastructure changes
- 🔄 Following security audits

### Rotation Procedure

#### 1. Generate New Secrets

```bash
# Generate new secrets
NEW_SECRET=$(python -c 'import secrets; print(secrets.token_urlsafe(32))')
NEW_JWT=$(python -c 'import secrets; print(secrets.token_urlsafe(32))')

echo "New SECRET_KEY: $NEW_SECRET"
echo "New JWT_SECRET_KEY: $NEW_JWT"
```

#### 2. Update Secrets Manager (Production)

```bash
# Update AWS Secrets Manager
aws secretsmanager update-secret \
    --secret-id codementor/production/secrets \
    --secret-string '{
        "SECRET_KEY": "<new-secret>",
        "JWT_SECRET_KEY": "<new-jwt-secret>",
        ...
    }'
```

#### 3. Rolling Restart (Zero Downtime)

```bash
# Kubernetes rolling restart
kubectl rollout restart deployment/codementor-backend

# Or AWS ECS force new deployment
aws ecs update-service \
    --cluster codementor-prod \
    --service codementor-backend \
    --force-new-deployment
```

#### 4. Invalidate Old Sessions (JWT Rotation)

When rotating JWT_SECRET_KEY, all existing user sessions will be invalidated. Users will need to log in again.

**Communication Template:**
```
Subject: Scheduled Maintenance - Re-login Required

We've completed scheduled security updates to CodeMentor.
Please log in again to continue using the platform.

This is a normal security procedure and your data is safe.
```

#### 5. Verify Rotation

```bash
# Check application logs for successful startup
kubectl logs -f deployment/codementor-backend | grep "Configuration loaded"

# Test login with new secrets
curl -X POST https://api.codementor.io/api/auth/login \
    -H "Content-Type: application/json" \
    -d '{"email":"test@example.com","password":"..."}'
```

---

## Pre-Commit Hooks (Automatic Protection)

### Installation

```bash
# Install pre-commit
pip install pre-commit

# Install hooks
pre-commit install

# Test hooks
pre-commit run --all-files
```

### What Pre-Commit Checks

1. **Detect Secrets:** Scans for accidentally committed secrets
2. **Block .env Files:** Prevents `.env` (but allows `.env.example`)
3. **Check File Sizes:** Blocks large files that might contain data dumps
4. **Code Quality:** Runs linters and formatters

**Example Blocked Commit:**

```bash
$ git commit -m "Add configuration"

Prevent .env files from being committed.......................Failed
- hook id: prevent-env-files
- exit code: 1

ERROR: .env files must NOT be committed!
Blocked files: .env

If you need to store configuration templates:
  1. Add values to .env.example instead
  2. Ensure .env is in .gitignore
  3. Use git rm --cached .env if already tracked
```

---

## Troubleshooting

### Problem: "SECRET_KEY must be at least 32 characters"

**Solution:**
```bash
# Generate a proper secret
python -c 'import secrets; print(secrets.token_urlsafe(32))'

# Update .env or environment variable
export SECRET_KEY=<generated-secret>
```

### Problem: "Production secret_key appears to be a development secret"

**Cause:** Using a weak secret like "changeme123..." in production.

**Solution:**
```bash
# Generate cryptographically secure secret
python -c 'import secrets; print(secrets.token_urlsafe(32))'

# NEVER use: changeme, password, secret, test, development, default
```

### Problem: "FRONTEND_URL must use HTTPS in production"

**Cause:** APP_ENV=production but FRONTEND_URL=http://...

**Solution:**
```bash
# Production MUST use HTTPS
export FRONTEND_URL=https://app.codementor.io
export BACKEND_URL=https://api.codementor.io

# For local testing, use development environment
export APP_ENV=development
```

### Problem: "GROQ_API_KEY is required in production"

**Cause:** Missing LLM API key when LLM_PRIMARY_PROVIDER=groq

**Solution:**
```bash
# Get API key from https://console.groq.com/
export GROQ_API_KEY=<your-api-key>

# Or switch to a different provider with configured key
export LLM_PRIMARY_PROVIDER=openai
export OPENAI_API_KEY=<your-openai-key>
```

### Problem: ".env file is tracked in git"

**Solution:**
```bash
# Remove from git tracking (keeps local file)
git rm --cached .env

# Commit the removal
git commit -m "Remove .env from git tracking"

# Verify it's in .gitignore
grep ".env" .gitignore

# If not in .gitignore, add it
echo ".env" >> .gitignore
git add .gitignore
git commit -m "Add .env to .gitignore"
```

### Problem: "Configuration validation fails at startup"

**Debugging Steps:**

```bash
# 1. Check environment variables are set
env | grep -E "SECRET_KEY|DATABASE_URL|REDIS_URL"

# 2. Test configuration loading
cd backend
python -c "
from src.config import Settings
try:
    settings = Settings()
    print('✓ Configuration valid!')
except Exception as e:
    print(f'✗ Configuration error: {e}')
"

# 3. Check application environment
echo $APP_ENV
# Should be: development, staging, or production

# 4. Run with verbose logging
LOG_LEVEL=DEBUG python -m src.app
```

---

## Security Best Practices

### DO:
✅ Use unique secrets for each environment (dev/staging/prod)
✅ Rotate secrets quarterly (every 90 days)
✅ Use AWS Secrets Manager or equivalent in production
✅ Generate secrets with `secrets.token_urlsafe(32)` or better
✅ Monitor secret access logs
✅ Revoke secrets immediately upon exposure
✅ Use different secrets for different purposes (JWT ≠ app secret)

### DON'T:
❌ Commit `.env` to git
❌ Share secrets via Slack, email, or unencrypted channels
❌ Reuse secrets across environments
❌ Use dictionary words or patterns in secrets
❌ Store secrets in code or documentation
❌ Give broad access to production secrets
❌ Forget to rotate after team changes

---

## References

- [OWASP Secrets Management Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html)
- [AWS Secrets Manager Documentation](https://docs.aws.amazon.com/secretsmanager/)
- [NIST SP 800-57: Key Management](https://csrc.nist.gov/publications/detail/sp/800-57-part-1/rev-5/final)
- [Python secrets module](https://docs.python.org/3/library/secrets.html)

---

## Document Control

**File Name:** secrets-management-guide.md
**Location:** /home/llmtutor/llm_tutor/docs/secrets-management-guide.md
**Version:** 1.0
**Date:** 2025-12-06
**Work Stream:** SEC-2 (Secrets Management)
**Classification:** Internal

**Related Documents:**
- `.env.example` - Configuration template
- `.pre-commit-config.yaml` - Pre-commit hooks
- `backend/src/config.py` - Configuration validation logic
- `backend/tests/test_secrets_management.py` - Security tests

---

**END OF DOCUMENT**
