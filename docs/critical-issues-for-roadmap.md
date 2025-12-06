# Critical Issues for Roadmap Escalation
# LLM Coding Tutor Platform

**Document Version:** 1.0
**Review Date:** 2025-12-06
**Source:** Architectural Review Report v1.0
**Priority:** P0-P1 Issues Requiring Roadmap Integration

---

## Executive Summary

This document identifies **critical and high-priority issues** discovered during the comprehensive architectural review that should be added to the project roadmap. These issues block production deployment or pose significant risks if not addressed.

**Total Issues:** 8 critical, 5 high-priority
**Estimated Effort:** 45 days total
**Recommended Staging:** 3 phases over 6 weeks

---

## Phase 1: Security Blockers (P0 - MUST FIX BEFORE PRODUCTION)

### Issue CRIT-1: Secrets Exposed in Git Repository

**Severity:** P0 - Critical Blocker
**Category:** Security - Secrets Management
**Estimated Effort:** 1 day (immediate) + 3 days (comprehensive fix)

**Description:**
The `.env` file containing production secrets is tracked in git:
- JWT secret key exposed
- Database credentials in git history
- Redis credentials exposed
- LLM API keys (GROQ) in git history

**Impact:**
- ⚠️ Complete authentication bypass possible (JWT secret exposed)
- ⚠️ Database compromise risk
- ⚠️ LLM API abuse ($10,000+ potential cost)
- ⚠️ Cannot rotate secrets without breaking git history

**Recommended Work Stream:** `SEC-2: Secrets Management`

**Tasks:**
1. **Immediate (Day 1):**
   - [ ] Remove `.env` from git tracking: `git rm --cached .env`
   - [ ] Create `.env.example` with placeholders
   - [ ] Commit removal of `.env`
   - [ ] Rotate ALL production secrets:
     - Generate new JWT secret (32+ chars)
     - Change database password
     - Change Redis password
     - Rotate GROQ API key

2. **Short-term (Days 2-4):**
   - [ ] Set up secrets management (AWS Secrets Manager, HashiCorp Vault, or GCP Secret Manager)
   - [ ] Purge `.env` from git history (BFG Repo-Cleaner)
   - [ ] Add pre-commit hook to prevent secret commits
   - [ ] Document secrets management in deployment guide
   - [ ] Use different secrets per environment (dev/staging/prod)

**Acceptance Criteria:**
- [ ] `.env` removed from git tracking
- [ ] `.env.example` created and committed
- [ ] All production secrets rotated
- [ ] Secrets manager configured
- [ ] Pre-commit hooks prevent future commits
- [ ] Documentation updated

**References:**
- AP-CRIT-001 (Hardcoded Configuration Values)
- Architectural Review Report: CRIT-1

---

### Issue CRIT-2: Email Verification Not Enforced

**Severity:** P0 - Critical Security Gap
**Category:** Security - Authorization
**Estimated Effort:** 2 days

**Description:**
The `require_verified_email` decorator exists but only contains a placeholder implementation. Unverified users can access email-protected resources.

**Location:** `/backend/src/middleware/auth_middleware.py:222-256`

**Impact:**
- ⚠️ Unverified users accessing protected features
- ⚠️ Spam/bot accounts not blocked
- ⚠️ Requirement REQ-AUTH-001 not fully implemented
- ⚠️ Security requirement documented but not enforced

**Recommended Work Stream:** `SEC-2-AUTH: Email Verification Enforcement`

**Tasks:**
1. **Implementation (Day 1):**
   - [ ] Complete `require_verified_email` decorator implementation
   - [ ] Query database for `email_verified` status
   - [ ] Return 403 error if not verified
   - [ ] Add comprehensive logging

2. **Email Workflow (Day 1-2):**
   - [ ] Implement email verification send on registration
   - [ ] Create verification token endpoint
   - [ ] Mark email as verified on token redemption
   - [ ] Add email resend functionality

3. **Testing (Day 2):**
   - [ ] Integration tests for email verification enforcement
   - [ ] Test protection on all relevant endpoints
   - [ ] Test email verification workflow end-to-end

4. **Audit (Day 2):**
   - [ ] Audit all routes to identify which require verified email
   - [ ] Add decorator to appropriate routes
   - [ ] Consider adding `email_verified` to JWT claims for performance

**Acceptance Criteria:**
- [ ] `require_verified_email` decorator fully implemented
- [ ] Email verification workflow complete
- [ ] Integration tests passing
- [ ] All appropriate routes protected
- [ ] Documentation updated

**References:**
- AP-CRIT-002 (Email Verification Missing)
- REQ-AUTH-001 (Email Verification Requirement)
- Architectural Review Report: CRIT-2

---

### Issue CRIT-3: Configuration Validation Incomplete

**Severity:** P0 - Production Blocker
**Category:** Security - Configuration
**Estimated Effort:** 4 hours

**Description:**
SEC-1 work stream added partial config validation (secret strength) but missing comprehensive production checks. Application can start with invalid or insecure configuration.

**Location:** `/backend/src/config.py`

**Impact:**
- ⚠️ Production deployed with weak secrets
- ⚠️ Missing critical configuration (DATABASE_URL, etc.)
- ⚠️ Development secrets used in production
- ⚠️ Runtime failures instead of startup failures

**Recommended Work Stream:** `SEC-2-CONFIG: Configuration Hardening`

**Tasks:**
1. **Production Validation (2 hours):**
   - [ ] Add `validate_production_config()` model validator
   - [ ] Require DATABASE_URL, REDIS_URL in production
   - [ ] Require LLM API key (GROQ_API_KEY)
   - [ ] Check secrets aren't development defaults ("changeme", "secret", etc.)

2. **URL Validation (1 hour):**
   - [ ] Validate DATABASE_URL format (PostgreSQL)
   - [ ] Validate REDIS_URL format
   - [ ] Validate frontend_url and backend_url are HTTPS in production

3. **OAuth Validation (1 hour):**
   - [ ] If OAuth enabled, require client IDs and secrets
   - [ ] Validate OAuth redirect URLs

**Acceptance Criteria:**
- [ ] Application fails fast on invalid production config
- [ ] All critical settings validated at startup
- [ ] Development secrets detected and rejected in production
- [ ] Clear error messages guide configuration fixes
- [ ] Tests verify validation logic

**Code Example:**

```python
@model_validator(mode='after')
def validate_production_config(self) -> 'Settings':
    if self.app_env == "production":
        # Require all critical services
        required = {
            "database_url": "DATABASE_URL",
            "redis_url": "REDIS_URL",
            "groq_api_key": "GROQ_API_KEY",
        }
        for field, env_var in required.items():
            if not getattr(self, field):
                raise ValueError(f"{env_var} required in production")

        # Validate secrets aren't dev defaults
        dev_secrets = ["changeme", "secret", "password", "test"]
        for secret_field in ["secret_key", "jwt_secret_key"]:
            value = getattr(self, secret_field).get_secret_value().lower()
            if any(dev in value for dev in dev_secrets):
                raise ValueError(f"{secret_field} appears to be development secret")

        # Require HTTPS in production
        if not self.frontend_url.startswith("https://"):
            raise ValueError("frontend_url must use HTTPS in production")

    return self
```

**References:**
- AP-CRIT-003 (Configuration Validation Missing)
- Architectural Review Report: CRIT-3

---

## Phase 2: High-Priority Security (P1 - FIX WITHIN 2 WEEKS)

### Issue HIGH-1: Rate Limiting Gaps on LLM Endpoints

**Severity:** P1 - High (Cost/DoS Risk)
**Category:** Security - Rate Limiting
**Estimated Effort:** 3 days

**Description:**
Not all LLM-invoking endpoints have rate limiting. Malicious users could spam expensive LLM requests, causing cost explosion.

**Affected Endpoints:**
- `/api/chat/send` - No rate limiting
- `/api/exercises/generate` - No rate limiting
- `/api/exercises/hint` - No rate limiting

**Impact:**
- ⚠️ LLM API cost explosion (potential $10K+/day)
- ⚠️ DoS attack on LLM quota
- ⚠️ Service degradation for legitimate users
- ⚠️ Violates REQ-SEC-007 (DDoS mitigation)

**Cost Analysis:**
- GROQ cost: ~$0.001/request
- Potential abuse: 10,000 requests/day/user × 100 users = 1M requests = $1,000/day
- Without limits: Could exceed monthly budget in hours

**Recommended Work Stream:** `SEC-3: Rate Limiting Enhancement`

**Tasks:**
1. **Implementation (Days 1-2):**
   - [ ] Add rate limiting decorator to all LLM endpoints
   - [ ] Implement tiered limits based on subscription (if applicable)
   - [ ] Set conservative limits:
     - Chat: 10 requests/minute, 100/hour
     - Exercise generation: 2 requests/minute, 50/day
     - Hints: 5 requests/minute, 30/hour
   - [ ] Add cost tracking per user

2. **Advanced Features (Day 3):**
   - [ ] Implement token bucket algorithm for burst handling
   - [ ] Add exponential backoff for retries
   - [ ] Set up cost limit alerts ($50/day threshold)
   - [ ] Create admin dashboard for rate limit monitoring

3. **Testing:**
   - [ ] Integration tests for rate limiting
   - [ ] Load testing to validate limits
   - [ ] Test rate limit error responses

**Acceptance Criteria:**
- [ ] All LLM endpoints have rate limiting
- [ ] Rate limits prevent cost abuse
- [ ] Clear error messages when limits exceeded
- [ ] Monitoring/alerting configured
- [ ] Tests validate rate limiting

**References:**
- AP-ARCH-002 (Missing Rate Limiting)
- Architectural Review Report: HIGH-1

---

### Issue HIGH-2: Insufficient Input Validation

**Severity:** P1 - High (Security Risk)
**Category:** Security - Input Validation
**Estimated Effort:** 5 days

**Description:**
Input validation inconsistent across endpoints. Some use Pydantic, others accept raw input without max length checks, risking storage exhaustion and XSS.

**Affected Endpoints:**
- `/api/chat/send` - No max length validation
- `/api/exercises/submit` - No max length validation
- `/api/users/profile` - Partial validation

**Impact:**
- ⚠️ Database overflow attacks (10MB chat message)
- ⚠️ Storage exhaustion
- ⚠️ XSS vulnerabilities in stored data
- ⚠️ Poor user experience (unclear limits)

**Recommended Work Stream:** `SEC-3-INPUT: Input Validation Hardening`

**Tasks:**
1. **Schema Creation (Days 1-2):**
   - [ ] Create Pydantic schemas for ALL request bodies
   - [ ] Define maximum lengths:
     - Chat messages: 10,000 characters
     - User bio: 1,000 characters
     - Career goals: 2,000 characters
     - Code submissions: 50,000 characters
     - Exercise descriptions: 5,000 characters

2. **Sanitization (Days 3-4):**
   - [ ] Add sanitization for user-generated content
   - [ ] Strip dangerous HTML/script tags (use `bleach` library)
   - [ ] Implement markdown sanitization
   - [ ] Add URL validation for GitHub URLs

3. **Implementation (Day 5):**
   - [ ] Apply schemas to all endpoints
   - [ ] Update error responses with clear validation messages
   - [ ] Add server-side validation matching frontend

4. **Testing:**
   - [ ] Test all endpoints with oversized input
   - [ ] Test XSS attack vectors
   - [ ] Test validation error responses

**Code Example:**

```python
from pydantic import BaseModel, Field, field_validator
import bleach

class ChatMessageSchema(BaseModel):
    message: str = Field(..., min_length=1, max_length=10000)
    conversation_id: Optional[int] = None

    @field_validator('message')
    @classmethod
    def sanitize_message(cls, v: str) -> str:
        allowed_tags = ['b', 'i', 'code', 'pre', 'a']
        cleaned = bleach.clean(v, tags=allowed_tags, strip=True)
        return cleaned.strip()
```

**Acceptance Criteria:**
- [ ] All endpoints have Pydantic schemas
- [ ] Maximum lengths enforced on all text fields
- [ ] XSS protection via sanitization
- [ ] Clear validation error messages
- [ ] Integration tests validate all limits

**References:**
- AP-SEC-002 (Input Sanitization Missing)
- Architectural Review Report: HIGH-2

---

### Issue HIGH-3: Missing CSRF Protection

**Severity:** P1 - High (Security Gap)
**Category:** Security - CSRF
**Estimated Effort:** 2 days

**Description:**
With SEC-1-FE migration to httpOnly cookies, CSRF protection becomes critical. Currently relying only on SameSite cookies, which isn't sufficient for all scenarios.

**Impact:**
- ⚠️ Cross-Site Request Forgery possible
- ⚠️ State-changing operations vulnerable
- ⚠️ Violates REQ-SEC-004 (CSRF protection required)

**Recommended Work Stream:** `SEC-3-CSRF: CSRF Protection`

**Tasks:**
1. **Analysis (Day 1 morning):**
   - [ ] Verify SameSite=strict cookies provide adequate protection
   - [ ] Identify scenarios where additional protection needed
   - [ ] Review browser compatibility for SameSite

2. **Implementation (Day 1-2):**
   - [ ] Add custom header requirement: `X-Requested-With: XMLHttpRequest`
   - [ ] Implement double-submit cookie pattern (if needed)
   - [ ] Add CSRF token generation endpoint
   - [ ] Update frontend to include custom headers

3. **Testing (Day 2):**
   - [ ] Test CSRF attack scenarios
   - [ ] Verify protection on all state-changing endpoints
   - [ ] Cross-browser testing

**Simple Solution (Recommended):**

```python
@app.before_request
async def csrf_protection():
    """Require custom header for state-changing requests."""
    if request.method in ["POST", "PUT", "DELETE", "PATCH"]:
        # Require X-Requested-With header (AJAX requests only)
        if not request.headers.get("X-Requested-With"):
            # Allow if has valid CSRF token header
            csrf_token = request.headers.get("X-CSRF-Token")
            csrf_cookie = request.cookies.get("csrf_token")

            if not (csrf_token and csrf_cookie and csrf_token == csrf_cookie):
                raise APIError("CSRF protection failed", status_code=403)
```

**Acceptance Criteria:**
- [ ] CSRF protection implemented
- [ ] All state-changing endpoints protected
- [ ] Frontend updated with CSRF tokens/headers
- [ ] Tests verify CSRF prevention
- [ ] Documentation updated

**References:**
- Architectural Review Report: HIGH-3
- OWASP CSRF Prevention Cheat Sheet

---

### Issue HIGH-4: Missing Production Monitoring

**Severity:** P1 - High (Operations)
**Category:** Observability - Monitoring
**Estimated Effort:** 5 days

**Description:**
No production monitoring or error tracking configured. Cannot detect, diagnose, or respond to production issues.

**Impact:**
- ⚠️ Downtime not detected until users complain
- ⚠️ Errors not tracked or triaged
- ⚠️ Performance degradation invisible
- ⚠️ Cannot debug production issues
- ⚠️ Violates operational best practices

**Recommended Work Stream:** `OPS-1: Production Monitoring Setup`

**Tasks:**
1. **Error Tracking (Day 1):**
   - [ ] Set up Sentry (or alternative: Rollbar, Bugsnag)
   - [ ] Integrate with backend (quart-sentry)
   - [ ] Configure error capture and deduplication
   - [ ] Set up error alerts (Slack/email)

2. **Application Metrics (Days 2-3):**
   - [ ] Add custom metrics tracking:
     - Request latency (p50, p95, p99)
     - LLM request count and cost
     - Database query performance
     - Active user count
   - [ ] Set up Prometheus/Grafana or cloud monitoring
   - [ ] Create dashboards for key metrics

3. **Health Check Monitoring (Day 3):**
   - [ ] Configure external uptime monitoring (UptimeRobot, Pingdom)
   - [ ] Add health check alerts
   - [ ] Monitor database/Redis connectivity
   - [ ] Set up PagerDuty/OpsGenie for on-call

4. **Alerting (Day 4):**
   - [ ] Configure alert thresholds:
     - Error rate > 5% for 5 minutes
     - Response time p95 > 2 seconds
     - LLM cost > $50/day
     - Health check failures
   - [ ] Set up alert routing (Slack, email, PagerDuty)
   - [ ] Create runbooks for common alerts

5. **Documentation (Day 5):**
   - [ ] Document monitoring setup
   - [ ] Create alert response procedures
   - [ ] Train team on monitoring tools

**Acceptance Criteria:**
- [ ] Error tracking operational (Sentry)
- [ ] Custom metrics collected
- [ ] Dashboards created
- [ ] Health check monitoring configured
- [ ] Alerting operational
- [ ] Documentation complete
- [ ] Team trained

**Recommended Tools:**
- **Error Tracking:** Sentry (free tier: 5K errors/month)
- **Metrics:** Prometheus + Grafana (open source) or CloudWatch
- **Uptime:** UptimeRobot (free tier: 50 monitors)
- **Alerting:** Slack webhooks (free) or PagerDuty

**References:**
- Architectural Review Report: HIGH-5
- REQ-TECH-STACK-005 (Monitoring requirement)

---

### Issue HIGH-5: Database Query Optimization Needed

**Severity:** P1 - High (Performance)
**Category:** Performance - Database
**Estimated Effort:** 3 days

**Description:**
Potential N+1 query problems and missing optimizations in relationship loading. No pagination on list endpoints.

**Impact:**
- ⚠️ Slow response times with large datasets
- ⚠️ Database overload under traffic
- ⚠️ Memory exhaustion (loading thousands of records)
- ⚠️ Poor user experience

**Recommended Work Stream:** `PERF-1: Database Optimization`

**Tasks:**
1. **Audit (Day 1):**
   - [ ] Profile all database queries
   - [ ] Identify N+1 query problems
   - [ ] Find missing pagination
   - [ ] Document slow queries (>100ms)

2. **Eager Loading (Day 1-2):**
   - [ ] Add `selectinload()` for relationships
   - [ ] Use `joinedload()` for one-to-one
   - [ ] Test query reduction

3. **Pagination (Day 2-3):**
   - [ ] Implement pagination on list endpoints:
     - `/api/chat/conversations`
     - `/api/exercises/history`
     - `/api/progress/history`
   - [ ] Add pagination metadata to responses
   - [ ] Frontend pagination support

4. **Caching (Day 3):**
   - [ ] Implement Redis caching for:
     - User profiles (5-minute TTL)
     - Exercise metadata (1-hour TTL)
     - Achievement definitions (24-hour TTL)
   - [ ] Add cache invalidation logic

5. **Monitoring (Day 3):**
   - [ ] Add slow query logging (>100ms)
   - [ ] Set up query performance dashboard
   - [ ] Add database connection pool monitoring

**Code Example:**

```python
# ✅ Eager loading with pagination
from sqlalchemy.orm import selectinload

@chat_bp.route("/conversations", methods=["GET"])
@require_auth
async def get_conversations():
    page = request.args.get("page", 1, type=int)
    page_size = min(request.args.get("page_size", 20, type=int), 100)

    query = (
        select(Conversation)
        .where(Conversation.user_id == g.user_id)
        .options(selectinload(Conversation.messages))  # Eager load
        .order_by(Conversation.updated_at.desc())
        .limit(page_size)
        .offset((page - 1) * page_size)
    )

    async with get_async_db_session() as session:
        result = await session.execute(query)
        conversations = result.scalars().all()

        total = await session.scalar(
            select(func.count()).select_from(Conversation)
            .where(Conversation.user_id == g.user_id)
        )

    return jsonify({
        "data": [c.to_dict() for c in conversations],
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total": total,
            "pages": (total + page_size - 1) // page_size
        }
    }), 200
```

**Acceptance Criteria:**
- [ ] All N+1 queries fixed
- [ ] Pagination on all list endpoints
- [ ] Query result caching implemented
- [ ] Slow query monitoring operational
- [ ] Performance improved (measured)

**References:**
- AP-ARCH-003 (N+1 Query Problem)
- AP-ARCH-002 (Missing Pagination)
- Architectural Review Report: HIGH-4

---

## Phase 3: Testing & Documentation (P2 - WITHIN 4 WEEKS)

### Issue MED-1: Incomplete Test Coverage

**Severity:** P2 - Medium
**Category:** Testing - Coverage
**Estimated Effort:** 10 days

**Description:**
Test coverage below 80% target (REQ-MAINT-001). Some tests have known failures. No E2E tests implemented.

**Current Status:**
- Backend: 16 test files, coverage unknown
- Frontend: 17 test files, some failures (71% pass on onboarding)
- E2E: Not implemented (Playwright mentioned but not set up)

**Impact:**
- ⚠️ Regressions may slip through CI/CD
- ⚠️ Cannot confidently deploy changes
- ⚠️ Real browser behavior not tested
- ⚠️ Integration bugs not caught

**Recommended Work Stream:** `QA-1: Test Coverage Improvement`

**Tasks:**
1. **Coverage Analysis (Day 1):**
   - [ ] Run backend coverage: `pytest --cov=src`
   - [ ] Run frontend coverage: `npm run test:coverage`
   - [ ] Identify untested code paths
   - [ ] Create coverage improvement plan

2. **Fix Failing Tests (Days 2-3):**
   - [ ] Fix frontend onboarding tests (10 failures)
   - [ ] Configure test database for backend
   - [ ] Fix any backend test failures

3. **Add Missing Tests (Days 4-7):**
   - [ ] Backend unit tests to reach 80%
   - [ ] Frontend component tests to reach 80%
   - [ ] Integration tests for critical APIs
   - [ ] Security tests (XSS, CSRF, SQL injection)

4. **E2E Tests (Days 8-10):**
   - [ ] Set up Playwright
   - [ ] Test critical user journeys:
     - Registration → Onboarding → First Exercise
     - Login → Chat → Hint
     - Exercise Submission → Feedback
     - OAuth Login
   - [ ] Add E2E tests to CI/CD

5. **Coverage Gates (Day 10):**
   - [ ] Add coverage reporting to CI/CD
   - [ ] Block PRs with decreased coverage
   - [ ] Set up coverage badges

**Acceptance Criteria:**
- [ ] Backend coverage ≥ 80%
- [ ] Frontend coverage ≥ 80%
- [ ] All tests passing
- [ ] E2E tests for critical flows
- [ ] Coverage gates in CI/CD

**References:**
- Architectural Review Report: MED-1
- REQ-MAINT-001 (80% coverage requirement)

---

### Issue MED-2: API Documentation Missing

**Severity:** P2 - Medium
**Category:** Documentation - API
**Estimated Effort:** 3 days

**Description:**
OpenAPI configured but not exposed. No Swagger UI endpoint. API documentation not published.

**Impact:**
- ⚠️ Poor developer experience
- ⚠️ Frontend devs must read code to understand API
- ⚠️ Integration partners cannot use API
- ⚠️ Difficult to maintain API consistency

**Recommended Work Stream:** `DOC-1: API Documentation`

**Tasks:**
1. **Enable Swagger UI (Day 1):**
   - [ ] Configure Quart-Schema to expose `/docs`
   - [ ] Add OpenAPI metadata (title, version, description)
   - [ ] Test Swagger UI loads

2. **Document Endpoints (Days 1-2):**
   - [ ] Add comprehensive docstrings to all endpoints
   - [ ] Include request/response examples
   - [ ] Document authentication requirements
   - [ ] Add error response documentation

3. **Generate Client SDKs (Day 3):**
   - [ ] Generate TypeScript client from OpenAPI spec
   - [ ] Test generated client
   - [ ] Publish API docs to public URL

**Acceptance Criteria:**
- [ ] Swagger UI accessible at `/docs`
- [ ] All endpoints documented
- [ ] Examples for all requests/responses
- [ ] TypeScript client generated
- [ ] Documentation published

**References:**
- Architectural Review Report: MED-2
- REQ-TECH-STACK-006 (API documentation requirement)

---

## Issue Summary

### Priority Distribution

| Priority | Count | Total Effort |
|----------|-------|--------------|
| P0 (Critical Blockers) | 3 | 4.5 days |
| P1 (High Priority) | 5 | 18 days |
| P2 (Medium Priority) | 2 | 13 days |
| **Total** | **10** | **35.5 days** |

### Recommended Phasing

**Phase 1 - Week 1 (Security Blockers):** 4.5 days
- CRIT-1: Secrets in git (1 day immediate + async work)
- CRIT-2: Email verification (2 days)
- CRIT-3: Config validation (0.5 days)

**Phase 2 - Weeks 2-3 (High Priority Security & Ops):** 18 days
- HIGH-1: Rate limiting (3 days)
- HIGH-2: Input validation (5 days)
- HIGH-3: CSRF protection (2 days)
- HIGH-4: Monitoring (5 days)
- HIGH-5: Database optimization (3 days)

**Phase 3 - Weeks 4-6 (Testing & Documentation):** 13 days
- MED-1: Test coverage (10 days)
- MED-2: API documentation (3 days)

### Work Stream Dependencies

```
SEC-2 (Secrets) → Must complete first (blocks deployment)
    ↓
SEC-2-AUTH (Email Verify) → Independent
SEC-2-CONFIG (Config) → Independent
    ↓
SEC-3 (Rate Limiting) → Depends on config
SEC-3-INPUT (Validation) → Independent
SEC-3-CSRF (CSRF) → Independent
    ↓
OPS-1 (Monitoring) → Can run in parallel
PERF-1 (DB Optimization) → Can run in parallel
    ↓
QA-1 (Testing) → After security fixes
DOC-1 (API Docs) → After security fixes
```

### Recommended Team Allocation

- **Security Engineer:** CRIT-1, CRIT-2, CRIT-3, HIGH-1, HIGH-2, HIGH-3
- **Backend Engineer:** HIGH-5 (DB optimization), support security
- **DevOps Engineer:** HIGH-4 (Monitoring), CRIT-1 (secrets management)
- **QA Engineer:** MED-1 (Test coverage), support security testing
- **Tech Writer:** MED-2 (API docs)

---

## Integration with Existing Roadmap

### Current Roadmap Status (from plans/roadmap.md v1.18)

- Stage 4: Daily Exercise System - ✅ COMPLETE
- Stage 4.5: Security & Production Readiness - ✅ MOSTLY COMPLETE
  - SEC-1: Security Hardening - ✅ COMPLETE
  - SEC-1-FE: Frontend Cookie Auth - ✅ COMPLETE
  - DB-OPT: Database Optimization - ✅ COMPLETE

### Recommended New Stage

**Stage 4.75: Production Readiness Completion**

Add new work streams from this review:
- SEC-2: Secrets Management (CRIT-1) - 4 days
- SEC-2-AUTH: Email Verification (CRIT-2) - 2 days
- SEC-2-CONFIG: Config Hardening (CRIT-3) - 0.5 days
- SEC-3: Rate Limiting Enhancement (HIGH-1) - 3 days
- SEC-3-INPUT: Input Validation (HIGH-2) - 5 days
- SEC-3-CSRF: CSRF Protection (HIGH-3) - 2 days
- OPS-1: Production Monitoring (HIGH-4) - 5 days
- PERF-1: Database Optimization (HIGH-5) - 3 days
- QA-1: Test Coverage (MED-1) - 10 days
- DOC-1: API Documentation (MED-2) - 3 days

**Total:** 37.5 days (can parallelize to ~6 weeks with team)

---

## Success Criteria

### Definition of Done for Stage 4.75

- [ ] All P0 issues resolved (CRIT-1, CRIT-2, CRIT-3)
- [ ] All P1 issues resolved (HIGH-1 through HIGH-5)
- [ ] Test coverage ≥ 80%
- [ ] API documentation published
- [ ] Production monitoring operational
- [ ] Security audit passed
- [ ] Load testing completed
- [ ] Deployment runbook documented

### Production Deployment Checklist

- [ ] Secrets in secrets manager (not git)
- [ ] Email verification enforced
- [ ] Configuration validated
- [ ] Rate limiting on all LLM endpoints
- [ ] Input validation on all endpoints
- [ ] CSRF protection enabled
- [ ] Monitoring and alerting configured
- [ ] Database queries optimized and paginated
- [ ] Test coverage ≥ 80%
- [ ] API documentation available
- [ ] E2E tests passing
- [ ] Load testing passed (1000+ concurrent users)
- [ ] Security scan passed (no critical vulnerabilities)
- [ ] Backup/recovery tested
- [ ] Deployment playbook verified

---

## Document Control

**File Name:** critical-issues-for-roadmap.md
**Location:** `/home/llmtutor/llm_tutor/docs/critical-issues-for-roadmap.md`
**Version:** 1.0
**Date:** 2025-12-06
**Status:** Final - Ready for Roadmap Integration

**Related Documents:**
- `/docs/architectural-review-report.md` - Source analysis
- `/docs/anti-patterns.md` - Anti-pattern documentation
- `/plans/roadmap.md` - Project roadmap (to be updated)
- `/plans/requirements.md` - Requirements specification

**Next Actions:**
1. Review with product owner
2. Prioritize and schedule work streams
3. Update `/plans/roadmap.md` with Stage 4.75
4. Assign work streams to engineers
5. Create JIRA/GitHub issues for tracking

---

**END OF DOCUMENT**
