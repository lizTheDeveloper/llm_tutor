# Security Remediation Plan - LLM Coding Tutor Platform

## Document Version: 1.0
## Date: 2025-12-05
## Status: ACTIVE - Phase 1 (Critical Fixes)
## Related: security-review-2025-12-05.md

---

## Executive Summary

This remediation plan addresses **23 security findings** identified in the comprehensive security review:
- **CRITICAL**: 3 findings (immediate action required)
- **HIGH**: 7 findings (address within 1-2 weeks)
- **MEDIUM**: 8 findings (address within 1 month)
- **LOW**: 5 findings (continuous improvement)

**Estimated Total Effort**: 3-4 weeks for critical and high priority items

**Key Stakeholders**:
- Security Lead: Responsible for oversight and validation
- Backend Team: Backend security implementations
- Frontend Team: Frontend security implementations
- DevOps: Infrastructure and deployment security

---

## Phase 1: Critical Security Fixes (IMMEDIATE - Week 1)

**Goal**: Eliminate critical vulnerabilities that pose immediate risk to user data and system integrity.

**Timeline**: 5-7 days
**Total Effort**: 16-20 hours
**Status**: ⚪ Not Started

### Task Group 1.1: Secrets Management (CRIT-01)

**Priority**: P0 (CRITICAL)
**Severity**: CRITICAL
**OWASP**: A02:2021 - Cryptographic Failures
**Owner**: Backend Engineer + DevOps
**Effort**: 4 hours
**Dependencies**: None

**Tasks**:
1. [ ] Generate strong secrets for all production keys
   - Use `python3 -c "import secrets; print(secrets.token_urlsafe(64))"` for each key
   - SECRET_KEY, JWT_SECRET_KEY (64 bytes each)
   - Document rotation schedule (90 days)

2. [ ] Create `.env.local` template and add to `.gitignore`
   - Add `.env`, `.env.local`, `.env.*.local`, `*.env` to `.gitignore`
   - Create `.env.example` with placeholder values
   - Document secret management process

3. [ ] Audit git history for committed secrets
   - Run: `git log -p | grep -i "secret_key\|api_key" > secret_audit.txt`
   - Review findings
   - If secrets found, rotate ALL secrets immediately
   - Consider git history rewrite if necessary (use BFG Repo-Cleaner)

4. [ ] Set up production secrets management
   - **Option A** (Cloud): Use GCP Secret Manager / AWS Secrets Manager
   - **Option B** (Self-hosted): Use HashiCorp Vault
   - **Option C** (Simple): Environment variables with restricted access
   - Update deployment scripts to use secrets manager
   - Document retrieval process in deployment docs

**Verification**:
- [ ] No secrets in `.env` file (only placeholders)
- [ ] `.env.local` in `.gitignore` and not committed
- [ ] All secrets 64+ characters, cryptographically random
- [ ] Secrets rotation policy documented
- [ ] Production secrets stored in secrets manager

**Done When**:
- All production secrets are strong, unique, and stored securely
- No secrets committed to git repository
- Secrets rotation policy established and documented

---

### Task Group 1.2: HTTPS/TLS Enforcement (CRIT-02)

**Priority**: P0 (CRITICAL)
**Severity**: CRITICAL
**OWASP**: A02:2021 - Cryptographic Failures
**Owner**: Backend Engineer + DevOps
**Effort**: 4 hours
**Dependencies**: None

**Tasks**:
1. [ ] Enable HSTS headers in production
   - Modify `backend/src/middleware/security_headers.py`
   - Uncomment and configure HSTS header:
     ```python
     if settings.app_env == "production":
         response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"
     ```
   - Add environment check to prevent HSTS in development

2. [ ] Configure secure session cookies
   - Verify in session configuration or add:
     ```python
     SESSION_COOKIE_SECURE = True  # Only send over HTTPS
     SESSION_COOKIE_HTTPONLY = True  # Prevent JavaScript access
     SESSION_COOKIE_SAMESITE = "Lax"  # CSRF protection
     ```
   - Make conditional on production environment

3. [ ] Update CORS origins for HTTPS
   - Modify `backend/src/config.py` to enforce HTTPS origins in production
   - Update `.env.example` with HTTPS examples
   - Add validation to reject HTTP origins in production

4. [ ] Set up HTTPS redirect (deployment configuration)
   - **Option A** (Reverse Proxy): Configure Nginx/Caddy to redirect HTTP → HTTPS
   - **Option B** (Application): Add Flask/Quart redirect middleware
   - Test redirect behavior

5. [ ] Obtain and configure SSL/TLS certificate
   - **Option A** (Cloud): Use managed certificate (GCP/AWS)
   - **Option B** (Let's Encrypt): Set up automatic renewal
   - Configure certificate in web server
   - Test certificate validity (ssllabs.com)

**Verification**:
- [ ] HSTS header present in production responses
- [ ] Session cookies have Secure, HttpOnly, SameSite flags
- [ ] HTTP requests redirect to HTTPS in production
- [ ] SSL/TLS certificate valid and trusted
- [ ] A+ rating on SSL Labs test

**Done When**:
- All traffic in production is HTTPS-only
- HSTS headers properly configured
- Session cookies secured with appropriate flags
- SSL/TLS certificate valid and auto-renewing

---

### Task Group 1.3: OAuth Token Security (CRIT-03)

**Priority**: P0 (CRITICAL)
**Severity**: CRITICAL
**OWASP**: A01:2021 - Broken Access Control
**Owner**: Backend Engineer
**Effort**: 6 hours
**Dependencies**: None

**Tasks**:
1. [ ] Replace URL parameters with fragment identifiers
   - Modify `backend/src/api/auth.py` (lines 322, 514)
   - Change from: `?code={temp_code}` to `#{temp_code}`
   - Update frontend to read from `window.location.hash`
   - Test OAuth flow with GitHub and Google

2. [ ] Implement PKCE (Proof Key for Code Exchange)
   - Generate code_verifier and code_challenge on authorization request:
     ```python
     code_verifier = secrets.token_urlsafe(64)
     code_challenge = base64.urlsafe_b64encode(
         hashlib.sha256(code_verifier.encode()).digest()
     ).decode().rstrip('=')
     ```
   - Store verifier in session
   - Send challenge to OAuth provider
   - Validate verifier on callback
   - Update OAuth provider configurations to support PKCE

3. [ ] Reduce temporary code TTL
   - Change from 5 minutes to 60 seconds
   - Update Redis expiration: `expire=60` (currently 300)
   - Test that normal flow still works within 60 seconds

4. [ ] Add OAuth security headers
   - Add `Referrer-Policy: no-referrer` to OAuth callback responses
   - Verify no code leakage in referer headers

**Verification**:
- [ ] OAuth codes not visible in browser URL bar
- [ ] OAuth codes not in browser history
- [ ] PKCE flow working for GitHub and Google OAuth
- [ ] Temporary codes expire in 60 seconds
- [ ] Referer policy prevents code leakage

**Done When**:
- OAuth codes transmitted via fragments, not query parameters
- PKCE implemented and functional
- Temporary codes have 60-second lifetime
- No code leakage via browser history or referer headers

---

### Task Group 1.4: Frontend Token Storage (HIGH-07 - promoted to Phase 1)

**Priority**: P0 (CRITICAL - promoted due to XSS risk)
**Severity**: HIGH
**OWASP**: A03:2021 - Injection
**Owner**: Backend Engineer + Frontend Engineer
**Effort**: 6 hours
**Dependencies**: Task Group 1.2 (HTTPS required for Secure cookies)

**Tasks**:
1. [ ] Backend: Implement httpOnly cookie authentication
   - Modify `backend/src/api/auth.py` login endpoint
   - Replace JSON token response with httpOnly cookies:
     ```python
     response.set_cookie(
         "access_token",
         value=tokens["access_token"],
         httponly=True,
         secure=True,
         samesite="Lax",
         max_age=86400,  # 24 hours
     )
     response.set_cookie(
         "refresh_token",
         value=tokens["refresh_token"],
         httponly=True,
         secure=True,
         samesite="Strict",
         max_age=2592000,  # 30 days
     )
     ```
   - Update registration, OAuth callbacks similarly
   - Add middleware to read tokens from cookies

2. [ ] Frontend: Remove localStorage token storage
   - Modify `frontend/src/services/authService.ts`
   - Remove all `localStorage.setItem('authToken', ...)` calls
   - Remove all `localStorage.getItem('authToken')` calls
   - Configure axios to send cookies:
     ```typescript
     const apiClient = axios.create({
       baseURL: API_BASE_URL,
       withCredentials: true,
       headers: { 'Content-Type': 'application/json' },
     });
     ```

3. [ ] Update CORS to support credentials
   - Verify `allow_credentials=True` in `backend/src/middleware/cors_handler.py`
   - Ensure CORS origins are specific (no wildcards with credentials)
   - Test cross-origin requests with credentials

4. [ ] Handle logout with cookie clearing
   - Add logout endpoint that clears cookies:
     ```python
     response.delete_cookie("access_token")
     response.delete_cookie("refresh_token")
     ```
   - Update frontend logout to call backend endpoint

5. [ ] Test authentication flow end-to-end
   - Test login with cookies
   - Test protected route access
   - Test refresh token flow
   - Test logout
   - Verify cookies not accessible via JavaScript (httpOnly)

**Verification**:
- [ ] No tokens in localStorage or sessionStorage
- [ ] Tokens set as httpOnly cookies
- [ ] Cookies have Secure flag (HTTPS-only)
- [ ] Cookies have appropriate SameSite values
- [ ] Authentication works with cookie-based tokens
- [ ] JavaScript cannot access tokens (httpOnly verified in DevTools)

**Done When**:
- All authentication tokens stored in httpOnly cookies
- No tokens in localStorage or sessionStorage
- Authentication flow functional with cookies
- Cookies properly secured with httpOnly, Secure, SameSite flags

---

## Phase 1 Completion Criteria

**Definition of Done**:
- [ ] All Phase 1 task groups complete (1.1, 1.2, 1.3, 1.4)
- [ ] All critical vulnerabilities remediated
- [ ] Verification steps passed for all tasks
- [ ] Security testing performed (see Testing section)
- [ ] Changes deployed to staging environment
- [ ] Security review performed on staging
- [ ] Approval from security lead to proceed to Phase 2

**Testing Requirements**:
- [ ] Manual testing of OAuth flow (GitHub, Google)
- [ ] Manual testing of authentication with httpOnly cookies
- [ ] SSL/TLS certificate validation (ssllabs.com)
- [ ] Verify no secrets in git history
- [ ] Browser testing (Chrome, Firefox, Safari) for cookie behavior
- [ ] Mobile testing for responsive HTTPS behavior

---

## Phase 2: High Priority Security Fixes (Week 2-3)

**Goal**: Address high-severity vulnerabilities that significantly impact security posture.

**Timeline**: 10-14 days
**Total Effort**: 24-32 hours
**Status**: ⚪ Not Started
**Prerequisites**: Phase 1 complete

### Task Group 2.1: CSRF Protection (HIGH-03 / MED-03)

**Priority**: P1 (HIGH)
**Severity**: MEDIUM (but critical for state-changing operations)
**OWASP**: A01:2021 - Broken Access Control
**Owner**: Backend Engineer
**Effort**: 4 hours
**Dependencies**: Phase 1 complete

**Tasks**:
1. [ ] Create CSRF protection middleware
   - Create `backend/src/middleware/csrf_protection.py`
   - Implement token generation tied to session
   - Implement token validation
   - Store tokens in Redis with session_id as key

2. [ ] Add CSRF decorator for state-changing endpoints
   - Create `@require_csrf` decorator
   - Apply to all POST, PUT, DELETE, PATCH endpoints
   - Exempt login/register endpoints (pre-authentication)

3. [ ] Create CSRF token endpoint
   - Add `/auth/csrf-token` endpoint
   - Return token after authentication
   - Tie to user session (JTI)

4. [ ] Frontend: Fetch and include CSRF token
   - Fetch token on app initialization (after login)
   - Include in axios default headers: `X-CSRF-Token`
   - Handle token refresh on expiration

**Verification**:
- [ ] CSRF tokens generated and validated correctly
- [ ] State-changing operations fail without valid CSRF token
- [ ] CSRF tokens tied to sessions (can't reuse across sessions)
- [ ] Frontend includes CSRF token in all state-changing requests

---

### Task Group 2.2: Enhanced JWT Security (HIGH-05)

**Priority**: P1 (HIGH)
**Severity**: HIGH
**OWASP**: A07:2021 - Identification and Authentication Failures
**Owner**: Backend Engineer
**Effort**: 4 hours
**Dependencies**: None

**Tasks**:
1. [ ] Add security claims to JWT
   - Modify `backend/src/services/auth_service.py` generate_jwt_token
   - Add `iss` (issuer): "codementor.io"
   - Add `aud` (audience): "codementor-api"
   - Add `nbf` (not before): current timestamp
   - Optional: Add client fingerprint (IP + User-Agent hash)

2. [ ] Update JWT verification
   - Modify verify_jwt_token to validate `iss` and `aud`
   - Add proper exception handling for InvalidAudienceError, InvalidIssuerError
   - Verify `nbf` claim

3. [ ] Update configuration
   - Add JWT_ISSUER and JWT_AUDIENCE to config
   - Update .env.example with new config values

**Verification**:
- [ ] JWTs include iss, aud, nbf claims
- [ ] JWTs with wrong audience rejected
- [ ] JWTs with wrong issuer rejected
- [ ] JWTs used before nbf timestamp rejected

---

### Task Group 2.3: Stricter Rate Limiting (HIGH-01 / MED-02)

**Priority**: P1 (HIGH)
**Severity**: HIGH
**OWASP**: A07:2021 - Identification and Authentication Failures
**Owner**: Backend Engineer
**Effort**: 5 hours
**Dependencies**: None

**Tasks**:
1. [ ] Implement account-based rate limiting
   - Create account rate limit function in `auth_service.py`
   - Track failed attempts per email address
   - Implement 5 failed attempts → 15 minute lockout
   - Store in Redis with email-based keys

2. [ ] Tighten global rate limits
   - Login: Reduce from 10/min to 5/min, 100/hr to 20/hr
   - Password reset: Set to 2/min, 5/hr
   - Email verification: Set to 3/hr per email

3. [ ] Implement progressive delays
   - Add exponential backoff on failed attempts
   - Delay = min(failed_attempts * 2, 10) seconds

4. [ ] Add rate limit monitoring
   - Log rate limit violations
   - Track repeat offenders
   - Add security event for excessive violations

**Verification**:
- [ ] Account locked after 5 failed login attempts
- [ ] Progressive delays working (2s, 4s, 6s, ...)
- [ ] Rate limits enforced on all authentication endpoints
- [ ] Rate limit violations logged

---

### Task Group 2.4: Input Sanitization (HIGH-02)

**Priority**: P1 (HIGH)
**Severity**: HIGH
**OWASP**: A03:2021 - Injection
**Owner**: Backend Engineer
**Effort**: 4 hours
**Dependencies**: None

**Tasks**:
1. [ ] Install and configure bleach
   - Add `bleach` to `requirements.txt`
   - Install: `pip install bleach`

2. [ ] Create sanitization utilities
   - Create `backend/src/utils/sanitization.py`
   - Implement `sanitize_text_input()` function
   - Implement `sanitize_html_input()` for rich text (if needed)

3. [ ] Add Pydantic validation schemas
   - Create validation schemas for user inputs
   - Add regex validators for name, bio, etc.
   - Enforce max lengths

4. [ ] Apply sanitization to all user inputs
   - Registration: name
   - Profile: bio, career_goals, learning_style
   - Chat: messages (careful not to break code formatting)
   - Exercise submissions

5. [ ] Frontend: Verify React escaping
   - Audit for any `dangerouslySetInnerHTML` usage
   - Remove or justify each instance
   - Document XSS prevention strategy

**Verification**:
- [ ] HTML tags stripped from name, bio fields
- [ ] JavaScript injection attempts sanitized
- [ ] Code samples in chat preserved correctly
- [ ] No `dangerouslySetInnerHTML` without justification
- [ ] XSS test payloads properly sanitized

---

### Task Group 2.5: Session Invalidation on Security Events (HIGH-03)

**Priority**: P1 (HIGH)
**Severity**: HIGH
**OWASP**: A07:2021 - Identification and Authentication Failures
**Owner**: Backend Engineer
**Effort**: 3 hours
**Dependencies**: None

**Tasks**:
1. [ ] Create session invalidation helper
   - Add `invalidate_on_security_event()` method to AuthService
   - Support events: password_change, email_change, role_change, email_verified

2. [ ] Trigger on email verification
   - Call invalidation when user verifies email
   - Force re-login with verified status

3. [ ] Trigger on email change
   - Invalidate all sessions when email is changed
   - Send notification to old and new email

4. [ ] Trigger on role change
   - Invalidate sessions when user role changes
   - Log security event

5. [ ] Add security event logging
   - Log all session invalidations
   - Include user_id, event type, timestamp, IP address

**Verification**:
- [ ] Sessions invalidated on email verification
- [ ] Sessions invalidated on email change
- [ ] Sessions invalidated on role change
- [ ] Security events logged correctly
- [ ] Users must re-login after security events

---

### Task Group 2.6: Content Security Policy (HIGH-06)

**Priority**: P1 (HIGH)
**Severity**: HIGH
**OWASP**: A05:2021 - Security Misconfiguration
**Owner**: Backend Engineer
**Effort**: 3 hours
**Dependencies**: None

**Tasks**:
1. [ ] Remove unsafe CSP directives
   - Modify `backend/src/middleware/security_headers.py`
   - Remove `unsafe-inline` and `unsafe-eval`
   - Implement nonce-based CSP

2. [ ] Generate CSP nonces per request
   - Add nonce generation in security headers middleware
   - Store nonce in `g.csp_nonce`
   - Include nonce in CSP header

3. [ ] Strict CSP for API endpoints
   - Use `default-src 'none'` for API-only endpoints
   - API endpoints don't need script execution

4. [ ] Remove deprecated X-XSS-Protection header
   - Remove `X-XSS-Protection` header (deprecated)
   - Rely on CSP instead

**Verification**:
- [ ] CSP header includes nonces, not unsafe-inline/unsafe-eval
- [ ] API endpoints have strict CSP (default-src 'none')
- [ ] CSP violations logged (if reporting configured)
- [ ] No functionality broken by strict CSP

---

### Task Group 2.7: CORS Security (HIGH-04)

**Priority**: P1 (HIGH)
**Severity**: HIGH
**OWASP**: A05:2021 - Security Misconfiguration
**Owner**: Backend Engineer
**Effort**: 3 hours
**Dependencies**: None

**Tasks**:
1. [ ] Add CORS origin validation
   - Create validator in `config.py`
   - Reject wildcards in production
   - Validate origin format (must start with http:// or https://)

2. [ ] Implement runtime origin checking
   - Add before_request hook to validate Origin header
   - Log unauthorized origin attempts
   - Don't set CORS headers for unauthorized origins

3. [ ] Document CORS configuration
   - Document allowed origins for each environment
   - Explain why each origin is allowed
   - Create process for adding new origins

**Verification**:
- [ ] Wildcard origins rejected in production
- [ ] Unauthorized origins blocked
- [ ] Unauthorized origin attempts logged
- [ ] CORS working for legitimate origins

---

## Phase 2 Completion Criteria

**Definition of Done**:
- [ ] All Phase 2 task groups complete (2.1-2.7)
- [ ] All high-priority vulnerabilities remediated
- [ ] Verification steps passed for all tasks
- [ ] Security testing performed
- [ ] Changes deployed to staging environment
- [ ] Security review performed on staging
- [ ] Approval from security lead to proceed to Phase 3

---

## Phase 3: Medium Priority Fixes (Month 2)

**Goal**: Address medium-severity vulnerabilities and strengthen security posture.

**Timeline**: 4 weeks (parallel with feature development)
**Total Effort**: 28-36 hours
**Status**: ⚪ Not Started
**Prerequisites**: Phase 2 complete

### Task Group 3.1: Security Monitoring & Alerting (MED-08)

**Priority**: P2 (MEDIUM)
**Owner**: Backend Engineer + DevOps
**Effort**: 6 hours

**Tasks**:
1. [ ] Implement SecurityMonitor class
2. [ ] Track security events (failed logins, rate limits, etc.)
3. [ ] Set up alerting for critical events
4. [ ] Create security event dashboard
5. [ ] Configure alert destinations (email, Slack, PagerDuty)

---

### Task Group 3.2: Request ID Correlation (MED-07)

**Priority**: P2 (MEDIUM)
**Owner**: Backend Engineer
**Effort**: 3 hours

**Tasks**:
1. [ ] Add request ID middleware
2. [ ] Include request IDs in all log messages
3. [ ] Return request ID in response headers
4. [ ] Update logging configuration

---

### Task Group 3.3: Account-Based Rate Limiting Enhancement (MED-02)

**Priority**: P2 (MEDIUM)
**Owner**: Backend Engineer
**Effort**: 4 hours

**Tasks**:
1. [ ] Enhance account rate limiting from Phase 2
2. [ ] Add IP-based rate limiting
3. [ ] Implement distributed rate limiting (Redis)
4. [ ] Add rate limit headers (X-RateLimit-Remaining, etc.)

---

### Task Group 3.4: Email Enumeration Prevention (MED-01)

**Priority**: P2 (MEDIUM)
**Owner**: Backend Engineer
**Effort**: 3 hours

**Tasks**:
1. [ ] Normalize registration response times
2. [ ] Return identical responses for existing/new users
3. [ ] Add timing attack protection
4. [ ] Test enumeration resistance

---

### Task Group 3.5: Error Message Sanitization (MED-04)

**Priority**: P2 (MEDIUM)
**Owner**: Backend Engineer
**Effort**: 4 hours

**Tasks**:
1. [ ] Create SensitiveDataFilter for logging
2. [ ] Sanitize exception messages in production
3. [ ] Audit all error responses for information leakage
4. [ ] Update error handling middleware

---

### Task Group 3.6: Database Query Timeout (MED-05)

**Priority**: P2 (MEDIUM)
**Owner**: Backend Engineer
**Effort**: 2 hours

**Tasks**:
1. [ ] Add query timeout configuration
2. [ ] Update database engine settings
3. [ ] Test timeout behavior
4. [ ] Monitor slow queries

---

### Task Group 3.7: Onboarding Data Security (MED-06)

**Priority**: P2 (MEDIUM)
**Owner**: Backend Engineer + Frontend Engineer
**Effort**: 4 hours

**Tasks**:
1. [ ] Create backend API for onboarding progress
2. [ ] Move progress storage from localStorage to backend
3. [ ] Remove localStorage onboarding data
4. [ ] Update frontend to use backend API

---

### Task Group 3.8: Email Rate Limiting (LOW-03 - promoted)

**Priority**: P2 (MEDIUM - promoted to prevent abuse)
**Owner**: Backend Engineer
**Effort**: 2 hours

**Tasks**:
1. [ ] Add email rate limiting function
2. [ ] Limit verification emails to 3/hour
3. [ ] Limit password reset emails to 3/hour
4. [ ] Log email rate limit violations

---

## Phase 3 Completion Criteria

**Definition of Done**:
- [ ] All Phase 3 task groups complete (3.1-3.8)
- [ ] All medium-priority vulnerabilities remediated
- [ ] Security monitoring operational
- [ ] Changes deployed to production
- [ ] Post-deployment security review

---

## Phase 4: Continuous Improvement (Ongoing)

**Goal**: Implement security best practices and maintain security posture over time.

**Timeline**: Ongoing
**Status**: ⚪ Not Started

### Task Group 4.1: Security Documentation

**Effort**: 4 hours

**Tasks**:
1. [ ] Create security.txt file
2. [ ] Document incident response procedures
3. [ ] Create security testing guide
4. [ ] Document secrets rotation process
5. [ ] Create security onboarding guide for developers

---

### Task Group 4.2: Dependency Scanning

**Effort**: 4 hours

**Tasks**:
1. [ ] Set up automated dependency scanning (Safety, npm audit)
2. [ ] Configure GitHub Dependabot
3. [ ] Create CI/CD security pipeline
4. [ ] Set up vulnerability alerting
5. [ ] Document patching process

---

### Task Group 4.3: Security Testing Suite

**Effort**: 8 hours

**Tasks**:
1. [ ] Create security test suite
2. [ ] Add tests for CSRF protection
3. [ ] Add tests for rate limiting
4. [ ] Add tests for JWT validation
5. [ ] Add tests for XSS prevention
6. [ ] Add tests for SQL injection prevention
7. [ ] Integrate into CI/CD

---

### Task Group 4.4: Security Hardening

**Effort**: 4 hours

**Tasks**:
1. [ ] Increase bcrypt rounds to 14
2. [ ] Add Subresource Integrity (SRI) for CDN resources
3. [ ] Configure security headers per environment
4. [ ] Review and minimize API surface area
5. [ ] Audit third-party dependencies

---

### Task Group 4.5: Penetration Testing

**Effort**: External (16-40 hours)

**Tasks**:
1. [ ] Schedule professional penetration test
2. [ ] Prepare testing environment
3. [ ] Provide tester access and documentation
4. [ ] Review findings
5. [ ] Remediate identified issues
6. [ ] Retest fixes

---

## Security Testing Strategy

### Automated Testing

**Phase 1-2 Testing**:
```bash
# Static analysis
bandit -r backend/src -ll
safety check --json
semgrep --config=p/owasp-top-ten backend/src

# Frontend security
npm audit --audit-level=moderate
```

**Integration Tests** (add to test suite):
- Test CSRF protection on state-changing operations
- Test rate limiting enforcement
- Test JWT claim validation
- Test input sanitization
- Test session invalidation on security events
- Test CORS origin validation

### Manual Testing

**Critical Verification**:
1. Verify no secrets in git repository
2. Test HTTPS enforcement and HSTS
3. Test OAuth flow security (no codes in URL)
4. Test httpOnly cookie authentication
5. Verify JWT cannot be forged
6. Test rate limiting (account and global)
7. Test XSS protection (try payload injection)
8. Test CSRF protection (cross-origin requests)

### External Testing

**Professional Penetration Test** (Phase 4):
- Schedule after Phase 2 complete
- Focus areas:
  - Authentication and session management
  - OAuth implementation
  - Input validation and injection
  - Authorization and access control
  - Rate limiting effectiveness
  - CSRF protection

---

## Monitoring & Metrics

### Security Metrics to Track

1. **Authentication Metrics**:
   - Failed login attempts per account
   - Rate limit violations
   - Session invalidations
   - Password reset requests

2. **Vulnerability Metrics**:
   - Open security findings (by severity)
   - Mean time to remediation
   - Dependency vulnerabilities
   - Security test coverage

3. **Operational Metrics**:
   - SSL/TLS certificate expiration
   - Secrets rotation status
   - Security event frequency
   - CSRF token validation failures

### Alerting Thresholds

**Immediate (PagerDuty/SMS)**:
- 10+ failed logins for single account in 1 minute
- 100+ rate limit violations from single IP in 5 minutes
- SSL certificate expiring in < 7 days

**High Priority (Slack/Email)**:
- 5+ failed login attempts for single account
- Secrets rotation overdue (> 90 days)
- New critical CVE in dependency

**Medium Priority (Email)**:
- Unusual security event patterns
- Rate limit violations above baseline

---

## Risk Management

### Residual Risks

After all phases complete, these risks remain:

1. **Zero-day vulnerabilities** in dependencies
   - Mitigation: Regular updates, monitoring security advisories

2. **Social engineering attacks**
   - Mitigation: User education, MFA (future), security awareness

3. **DDoS attacks**
   - Mitigation: Rate limiting (partial), CDN/WAF (future)

4. **Insider threats**
   - Mitigation: Access controls, audit logging, least privilege

### Risk Acceptance

The following low-priority items may be deferred:

- Increasing bcrypt rounds (performance impact requires testing)
- Subresource Integrity (low risk for internal resources)
- Advanced security monitoring (basic monitoring sufficient initially)

---

## Rollback Plan

### If Critical Issue Occurs During Remediation

1. **Immediate**:
   - Revert to last known good deployment
   - Assess impact and scope
   - Notify stakeholders

2. **Short-term**:
   - Identify root cause
   - Determine fix or rollback strategy
   - Test fix in staging

3. **Long-term**:
   - Post-incident review
   - Update remediation plan
   - Improve testing strategy

### Rollback Triggers

- Authentication completely broken (users cannot login)
- Data loss or corruption
- Performance degradation > 50%
- Critical functionality broken (> 2 severity-1 bugs)

---

## Success Criteria

### Phase 1 Success

- [ ] No critical vulnerabilities (severity: CRITICAL)
- [ ] SSL Labs A+ rating
- [ ] All authentication flows secure (httpOnly cookies, HTTPS)
- [ ] No secrets in git repository
- [ ] OAuth implementation secure (no code leakage)

### Phase 2 Success

- [ ] No high-severity vulnerabilities
- [ ] CSRF protection operational
- [ ] JWT security enhanced
- [ ] Rate limiting effective against brute force
- [ ] Input sanitization preventing XSS
- [ ] CSP preventing inline script injection

### Phase 3 Success

- [ ] Security monitoring and alerting operational
- [ ] All medium-severity vulnerabilities remediated
- [ ] Request correlation in place for incident investigation
- [ ] Email enumeration prevented

### Phase 4 Success

- [ ] Continuous security testing in CI/CD
- [ ] Dependency scanning operational
- [ ] Professional penetration test passed
- [ ] Security documentation complete
- [ ] Incident response procedures documented

---

## Resource Requirements

### Personnel

**Phase 1** (Week 1):
- 1 Backend Engineer (full-time, 5 days)
- 1 Frontend Engineer (part-time, 2 days)
- 1 DevOps Engineer (part-time, 2 days)

**Phase 2** (Weeks 2-3):
- 1 Backend Engineer (full-time, 10 days)
- 1 Frontend Engineer (part-time, 1 day)

**Phase 3** (Month 2):
- 1 Backend Engineer (part-time, 50% over 4 weeks)
- 1 DevOps Engineer (part-time, 25% over 4 weeks)

**Phase 4** (Ongoing):
- Security review in sprint planning
- Penetration testing (external vendor)

### Infrastructure

- Secrets management service (GCP Secret Manager, AWS Secrets Manager, or Vault)
- SSL/TLS certificate (Let's Encrypt or managed certificate)
- Security monitoring tools (optional: Datadog, Grafana, ELK)
- Penetration testing budget ($5,000-$15,000)

---

## Timeline Summary

| Phase | Duration | Effort | Start Date | Target Completion |
|-------|----------|--------|------------|-------------------|
| Phase 1 (Critical) | 1 week | 20 hours | TBD | +1 week |
| Phase 2 (High) | 2 weeks | 28 hours | +1 week | +3 weeks |
| Phase 3 (Medium) | 4 weeks | 32 hours | +3 weeks | +7 weeks |
| Phase 4 (Ongoing) | Continuous | Varies | +7 weeks | Ongoing |

**Total Time to Secure Baseline**: 7 weeks (Phases 1-3)

---

## Document Control

**File Name**: security-remediation-plan.md
**Location**: /Users/annhoward/src/llm_tutor/plans/security-remediation-plan.md
**Version**: 1.0
**Date**: 2025-12-05
**Status**: Active - Awaiting Phase 1 Approval
**Classification**: Internal - Security Sensitive

**Related Documents**:
- `/reviews/security-review-2025-12-05.md` - Source security review
- `/plans/roadmap.md` - Project roadmap
- `/plans/requirements.md` - Feature requirements

**Approval Required**:
- [ ] Security Lead
- [ ] Engineering Manager
- [ ] Product Manager (for timeline impact)

---

**END OF DOCUMENT**
