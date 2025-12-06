# Anti-Patterns Checklist
## LLM Coding Tutor Platform (CodeMentor)

**Document Version:** 1.0  
**Created:** 2025-12-06  
**Purpose:** Prevent recurring architectural and security anti-patterns during development

---

## How to Use This Checklist

This checklist documents anti-patterns found in the codebase and provides guidelines to avoid them in future development. Review this checklist:

- **Before starting new features:** Check relevant sections for patterns to avoid
- **During code review:** Verify new code doesn't introduce listed anti-patterns
- **Monthly:** Review and update with newly discovered patterns

**Severity Levels:**
- **CRITICAL (P0):** Deployment blocker, must fix immediately
- **HIGH (P1):** Security/performance risk, fix before production
- **MEDIUM (P2):** Maintainability issue, fix in next sprint
- **LOW (P3):** Nice-to-have improvement, backlog

---

## 1. Security Anti-Patterns

### AP-SEC-001: Secrets in Git Repository (CRITICAL)

**What:** Committing secrets, API keys, or production URLs to git  
**Why It's Bad:** Public exposure, difficult to rotate, compliance violations  
**Status:** ❌ **FOUND** - `frontend/.env.production` tracked in git with production IP

**Example (BAD):**
```bash
# frontend/.env.production (tracked in git!)
VITE_API_BASE_URL=http://35.209.246.229/api/v1
VITE_ENV=production
```

**How to Avoid:**
```bash
# ✅ .gitignore should have:
.env
*.env
!.env.example

# ✅ Create .env.example with placeholders:
VITE_API_BASE_URL=https://api.example.com/api/v1
VITE_ENV=production

# ✅ Document in README.md:
"Copy .env.example to .env.production and fill in actual values"
```

**Detection:**
```bash
# Check for tracked .env files:
git ls-files | grep -E "\.env$|\.env\..+" | grep -v "\.env\.example"

# Check for hardcoded secrets:
git grep -E "api_key|password|secret|token" -- "*.env*"
```

**Remediation:**
```bash
# Remove from git history:
git filter-branch --tree-filter 'rm -f frontend/.env.production' HEAD
git push --force

# Update .gitignore:
echo "*.env.production" >> .gitignore

# Rotate any exposed secrets immediately
```

---

### AP-SEC-002: Placeholder Security Implementation (CRITICAL)

**What:** Decorator or security check that logs but doesn't enforce  
**Why It's Bad:** False sense of security, allows unauthorized access  
**Status:** ❌ **FOUND** - `require_verified_email` decorator is placeholder

**Example (BAD):**
```python
def require_verified_email(function: Callable) -> Callable:
    @wraps(function)
    async def wrapper(*args, **kwargs):
        # TODO: In a full implementation, we would fetch user from database
        logger.debug("Email verification check (placeholder)")
        return await function(*args, **kwargs)  # ⚠️ Doesn't actually check!
    return wrapper
```

**How to Avoid:**
```python
# ✅ Full implementation:
def require_verified_email(function: Callable) -> Callable:
    @wraps(function)
    async def wrapper(*args, **kwargs):
        if not hasattr(g, "user_id"):
            raise APIError("Authentication required", status_code=401)
        
        # ACTUALLY CHECK EMAIL VERIFICATION
        async with get_async_db_session() as session:
            user = await session.get(User, g.user_id)
            if not user or not user.email_verified:
                logger.warning("Unverified email access attempt", 
                              extra={"user_id": g.user_id})
                raise APIError("Email verification required", status_code=403)
        
        return await function(*args, **kwargs)
    return wrapper
```

**Detection:**
- Code review: Search for "TODO", "placeholder", "In a full implementation"
- Testing: Write tests that verify security is actually enforced

**Prevention:**
- Never merge security code with "TODO" or "placeholder" comments
- Write tests BEFORE implementing security features (TDD)
- Security features must be complete or not exist (no partial implementations)

---

### AP-SEC-003: Token Storage in localStorage (RESOLVED ✅)

**What:** Storing JWT tokens in browser localStorage  
**Why It's Bad:** Vulnerable to XSS attacks (JavaScript can read localStorage)  
**Status:** ✅ **RESOLVED** - SEC-1-FE work stream implemented httpOnly cookies

**Example (BAD - OLD):**
```typescript
// ❌ DON'T DO THIS
localStorage.setItem('access_token', token);
const token = localStorage.getItem('access_token');
```

**How to Avoid (CURRENT):**
```typescript
// ✅ Backend sets httpOnly cookie (frontend can't access via JavaScript)
// backend/src/api/auth.py
response.set_cookie(
    "access_token",
    access_token,
    httponly=True,      # Prevents JavaScript access (XSS protection)
    secure=True,        # HTTPS only
    samesite="strict",  # CSRF protection
    max_age=24 * 3600
)

// ✅ Frontend: Cookies sent automatically, no storage needed
// axios automatically includes cookies with credentials: 'include'
```

**Key Rule:** Never store sensitive tokens in localStorage/sessionStorage. Always use httpOnly cookies for authentication tokens.

---

### AP-SEC-004: Weak Password Validation

**What:** Allowing weak passwords (short, no complexity requirements)  
**Why It's Bad:** Enables brute force attacks, account takeovers  
**Status:** ✅ **GOOD** - Strong validation implemented

**Current Implementation (GOOD):**
```python
PASSWORD_REGEX = re.compile(
    r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]{12,}$"
)

# Requires:
# - Minimum 12 characters
# - At least one lowercase letter
# - At least one uppercase letter
# - At least one digit
# - At least one special character (@$!%*?&)
```

**Checklist for New Authentication Features:**
- [ ] Password minimum 12 characters
- [ ] Enforce mixed case, numbers, symbols
- [ ] Check against common password lists (e.g., rockyou.txt)
- [ ] Rate limit login attempts (prevent brute force)
- [ ] Lock account after N failed attempts
- [ ] Email notification on password change

---

### AP-SEC-005: Missing Rate Limiting on Expensive Endpoints

**What:** No rate limits on endpoints that call expensive external APIs  
**Why It's Bad:** Cost abuse, DoS attacks, budget exhaustion  
**Status:** ❌ **FOUND** - LLM endpoints not rate limited

**Example (BAD - CURRENT):**
```python
@chat_bp.route("/send", methods=["POST"])
@require_auth
async def send_message():
    # ⚠️ No rate limit! User can spam LLM calls
    message = data["message"]
    response = await LLMService.generate_response(message)  # $0.01-0.10 per call
    return jsonify(response), 200
```

**How to Avoid:**
```python
from src.middleware.rate_limiter import rate_limit

@chat_bp.route("/send", methods=["POST"])
@require_auth
@rate_limit(tier_limits={
    "free": "10/hour",
    "basic": "100/hour",
    "premium": "1000/hour"
})
async def send_message():
    message = data["message"]
    response = await LLMService.generate_response(message)
    return jsonify(response), 200
```

**Endpoints Requiring Rate Limits:**
- `/api/chat/send` - LLM calls ($$$)
- `/api/exercises/generate` - LLM exercise generation ($$$)
- `/api/exercises/{id}/hint` - LLM hints ($$$)
- `/api/auth/login` - Prevent brute force (security)
- `/api/auth/register` - Prevent account spam (abuse)
- `/api/github/review` - GitHub API quota (abuse)

**Rate Limit Strategy:**
- Free tier: Strict limits (10 LLM calls/hour)
- Basic tier: Moderate (100 LLM calls/hour)
- Premium tier: Generous (1000 LLM calls/hour)
- Admin tier: No limit (or very high limit)

---

### AP-SEC-006: Input Validation Inconsistency

**What:** Some endpoints validate input with Pydantic, others use manual checks  
**Why It's Bad:** Injection attacks, XSS, data corruption, hard to audit  
**Status:** ⚠️ **FOUND** - Inconsistent across endpoints

**Example (INCONSISTENT):**
```python
# ✅ Good: Uses Pydantic schema
@exercises_bp.route("/", methods=["POST"])
@require_auth
async def create_exercise():
    data = CreateExerciseRequest(**await request.get_json())  # Validated!
    exercise = await ExerciseService.create(data)
    return jsonify(exercise), 201

# ❌ Bad: Manual validation
@chat_bp.route("/send", methods=["POST"])
@require_auth
async def send_message():
    data = await request.get_json()
    message = data.get("message")  # No validation!
    if not message:  # Only checks existence, not length/format
        return jsonify({"error": "Message required"}), 400
```

**How to Avoid:**
```python
# ✅ ALWAYS use Pydantic for request validation
from pydantic import BaseModel, Field

class SendMessageRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=5000)
    context_type: Optional[str] = Field(None, regex="^(exercise|general|hint)$")

@chat_bp.route("/send", methods=["POST"])
@require_auth
async def send_message():
    data = SendMessageRequest(**await request.get_json())
    response = await LLMService.generate_response(data.message, data.context_type)
    return jsonify(response), 200
```

**Pydantic Best Practices:**
- `min_length` and `max_length` on all string fields
- `regex` for enums/patterns (email, phone, etc.)
- `conint` for integer ranges (e.g., `conint(ge=0, le=100)`)
- `conlist` for array length limits
- Custom validators for complex business logic

**Detection:**
```bash
# Find endpoints without Pydantic schemas:
grep -n "await request.get_json()" backend/src/api/*.py | \
  grep -v "BaseModel\|Request("
```

---

## 2. Architecture Anti-Patterns

### AP-ARCH-001: God Object (Large Service Classes)

**What:** Service class with 500+ lines doing too many things  
**Why It's Bad:** Hard to test, maintain, understand; violates Single Responsibility Principle  
**Status:** ⚠️ **FOUND** - `ExerciseService` (600+ lines)

**Example (BAD):**
```python
class ExerciseService:
    """Handles exercise generation, evaluation, hints, difficulty, templates, etc."""
    
    def generate_exercise(self):  # 50 lines
    def evaluate_solution(self):  # 40 lines
    def generate_hint(self):  # 30 lines
    def adjust_difficulty(self):  # 40 lines
    def create_template(self):  # 35 lines
    def grade_submission(self):  # 50 lines
    # ... 10 more methods, 600+ lines total
```

**How to Avoid:**
```python
# ✅ Split into focused services (SRP - Single Responsibility Principle)

class ExerciseGenerator:
    """Responsible only for generating new exercises."""
    def generate_personalized_exercise(self, user_profile):
        pass
    def generate_from_template(self, template_id):
        pass

class ExerciseEvaluator:
    """Responsible only for evaluating exercise solutions."""
    def evaluate_solution(self, exercise_id, solution):
        pass
    def calculate_score(self, test_results):
        pass

class HintService:
    """Responsible only for generating hints."""
    def generate_hint(self, exercise_id, user_attempt):
        pass
    def get_progressive_hints(self, exercise_id):
        pass

class DifficultyAdapter:
    """Responsible only for adaptive difficulty."""
    def adjust_difficulty(self, user_id, performance_data):
        pass
    def recommend_next_difficulty(self, user_id):
        pass
```

**Rule of Thumb:**
- Service class should be <300 lines
- Class should have one primary responsibility
- If class name needs "and" or "Manager", consider splitting

---

### AP-ARCH-002: Magic Numbers

**What:** Hardcoded values scattered throughout code  
**Why It's Bad:** Hard to change, inconsistencies, unclear intent  
**Status:** ⚠️ **FOUND** - Multiple locations

**Example (BAD):**
```python
# ❌ Magic numbers scattered
@rate_limit(60, 10)  # What do these numbers mean?
async def api_endpoint():
    pass

redis_client.setex(key, 3600, value)  # Why 3600?
if len(password) < 12:  # Why 12?
```

**How to Avoid:**
```python
# ✅ Extract to constants with descriptive names

# config.py or constants.py
class RateLimits:
    FREE_TIER_PER_MINUTE = 60
    FREE_TIER_BURST = 10
    BASIC_TIER_PER_MINUTE = 120
    BASIC_TIER_BURST = 20

class CacheTTL:
    USER_PROFILE = 300  # 5 minutes
    EXERCISE_TEMPLATE = 3600  # 1 hour
    LLM_RESPONSE = 7200  # 2 hours

class PasswordPolicy:
    MIN_LENGTH = 12
    REQUIRE_UPPERCASE = True
    REQUIRE_LOWERCASE = True
    REQUIRE_DIGIT = True
    REQUIRE_SPECIAL = True

# Usage
@rate_limit(RateLimits.FREE_TIER_PER_MINUTE, RateLimits.FREE_TIER_BURST)
async def api_endpoint():
    pass

redis_client.setex(key, CacheTTL.USER_PROFILE, value)
if len(password) < PasswordPolicy.MIN_LENGTH:
    raise APIError("Password too short")
```

**Common Magic Numbers to Extract:**
- Rate limits (requests per minute/hour)
- Cache TTLs (time to live in seconds)
- Pagination limits (page size, max results)
- Timeouts (connection, read, write)
- Retry counts and backoff times
- Password/validation rules
- File size limits
- Connection pool sizes

---

### AP-ARCH-003: Missing Pagination

**What:** Endpoints that return all results without pagination  
**Why It's Bad:** Memory exhaustion, slow responses, poor UX as data grows  
**Status:** ❌ **FOUND** - `/api/exercises/history`, `/api/progress/history`

**Example (BAD):**
```python
@exercises_bp.route("/history", methods=["GET"])
@require_auth
async def get_exercise_history():
    # ❌ Returns ALL exercises (could be thousands!)
    async with get_async_db_session() as session:
        result = await session.execute(
            select(UserExercise).where(UserExercise.user_id == g.user_id)
        )
        exercises = result.scalars().all()
        return jsonify([e.to_dict() for e in exercises]), 200
```

**How to Avoid:**
```python
# ✅ Implement cursor-based pagination
from pydantic import BaseModel, Field

class PaginationParams(BaseModel):
    limit: int = Field(50, ge=1, le=100)  # Max 100 per page
    offset: int = Field(0, ge=0)

@exercises_bp.route("/history", methods=["GET"])
@require_auth
async def get_exercise_history():
    params = PaginationParams(**request.args)
    
    async with get_async_db_session() as session:
        # Get total count (for pagination metadata)
        count_result = await session.execute(
            select(func.count()).select_from(UserExercise)
            .where(UserExercise.user_id == g.user_id)
        )
        total = count_result.scalar()
        
        # Get paginated results
        result = await session.execute(
            select(UserExercise)
            .where(UserExercise.user_id == g.user_id)
            .order_by(UserExercise.created_at.desc())
            .limit(params.limit)
            .offset(params.offset)
        )
        exercises = result.scalars().all()
        
        return jsonify({
            "data": [e.to_dict() for e in exercises],
            "pagination": {
                "total": total,
                "limit": params.limit,
                "offset": params.offset,
                "has_next": (params.offset + params.limit) < total
            }
        }), 200
```

**Pagination Checklist:**
- [ ] All list endpoints have pagination
- [ ] Default limit (e.g., 50 items)
- [ ] Maximum limit enforced (e.g., 100 items)
- [ ] Return total count for UI pagination
- [ ] Return `has_next` flag for infinite scroll
- [ ] Sort by a stable field (id, created_at) for consistent ordering

---

### AP-ARCH-004: Dual Database Engines (RESOLVED ✅)

**What:** Creating both sync and async database engines  
**Why It's Bad:** Double connection pool usage, wasted resources  
**Status:** ✅ **RESOLVED** - DB-OPT work stream removed sync engine

**Example (BAD - OLD):**
```python
class DatabaseManager:
    def __init__(self):
        # ❌ Both engines created (40 connections total!)
        self._sync_engine = create_engine(database_url)  # 20 connections
        self._async_engine = create_async_engine(async_url)  # 20 connections
```

**How to Avoid (CURRENT):**
```python
class DatabaseManager:
    def __init__(self):
        # ✅ Only async engine (20 connections)
        self._async_engine = create_async_engine(async_url)
        
# For migrations (Alembic), use separate sync engine:
def get_sync_engine_for_migrations(database_url):
    """Create sync engine ONLY for migrations."""
    return create_engine(database_url, pool_size=5)
```

**Key Rule:** In async applications, use async engines only. Create sync engines only when absolutely necessary (migrations) with small pool sizes.

---

### AP-ARCH-005: No Error Codes

**What:** Error responses only have messages, no machine-readable codes  
**Why It's Bad:** Frontend can't distinguish error types, difficult to handle programmatically  
**Status:** ⚠️ **FOUND** - Most errors lack error codes

**Example (BAD):**
```python
return jsonify({"error": "Authentication failed"}), 401
# Frontend can't tell if it's wrong password vs expired token vs invalid format
```

**How to Avoid:**
```python
# ✅ Add error codes
class ErrorCode:
    AUTH_INVALID_CREDENTIALS = "AUTH_001"
    AUTH_TOKEN_EXPIRED = "AUTH_002"
    AUTH_TOKEN_INVALID = "AUTH_003"
    AUTH_EMAIL_NOT_VERIFIED = "AUTH_004"
    
    DB_CONNECTION_FAILED = "DB_001"
    DB_CONSTRAINT_VIOLATION = "DB_002"
    
    LLM_API_ERROR = "LLM_001"
    LLM_RATE_LIMIT = "LLM_002"
    LLM_QUOTA_EXCEEDED = "LLM_003"

return jsonify({
    "error": "Authentication failed",
    "error_code": ErrorCode.AUTH_INVALID_CREDENTIALS,
    "details": "Invalid email or password"
}), 401

# Frontend can now handle specific errors:
if (error.error_code === "AUTH_002") {
    // Token expired -> refresh token flow
} else if (error.error_code === "AUTH_001") {
    // Invalid credentials -> show error message
}
```

---

## 3. Performance Anti-Patterns

### AP-PERF-001: N+1 Query Problem

**What:** Loading related data in a loop instead of eager loading  
**Why It's Bad:** 1 query becomes N+1 queries, slow response times  
**Status:** ⚠️ **RISK** - No explicit eager loading configured

**Example (BAD):**
```python
# ❌ N+1 queries (1 + 100 = 101 queries for 100 exercises)
exercises = await session.execute(
    select(Exercise).where(Exercise.user_id == user_id)
)
for exercise in exercises.scalars():
    # This triggers a separate query for EACH exercise!
    hints = await exercise.hints
```

**How to Avoid:**
```python
# ✅ Eager loading with selectinload (2 queries total)
from sqlalchemy.orm import selectinload

exercises_result = await session.execute(
    select(Exercise)
    .where(Exercise.user_id == user_id)
    .options(selectinload(Exercise.hints))  # Load hints in single query
)
exercises = exercises_result.scalars().all()

for exercise in exercises:
    hints = exercise.hints  # Already loaded, no query!
```

**Eager Loading Strategies:**
- `selectinload()` - Separate IN query (good for one-to-many)
- `joinedload()` - JOIN query (good for one-to-one)
- `subqueryload()` - Subquery (legacy, rarely needed)

---

### AP-PERF-002: Missing Database Indexes

**What:** Queries on columns without indexes  
**Why It's Bad:** Full table scans, slow queries as data grows  
**Status:** ✅ **RESOLVED** - DB-OPT work stream added indexes

**Indexes Added (GOOD):**
```sql
CREATE INDEX idx_users_role ON users(role);
CREATE INDEX idx_users_is_active ON users(is_active);
CREATE INDEX idx_exercises_difficulty ON exercises(difficulty);
CREATE INDEX idx_user_exercises_user_created ON user_exercises(user_id, created_at);
```

**Checklist for New Tables:**
- [ ] Index on foreign keys (user_id, exercise_id, etc.)
- [ ] Index on frequently queried fields (status, role, is_active)
- [ ] Composite index on WHERE + ORDER BY combinations
- [ ] Index on date fields used for filtering/sorting

**Don't Over-Index:**
- Avoid indexing low-cardinality fields (e.g., boolean with only true/false)
- Each index slows down writes (INSERT, UPDATE, DELETE)
- Rule of thumb: 3-5 indexes per table, not 10+

---

### AP-PERF-003: No Query Result Caching

**What:** Every request hits database even for static/infrequently changing data  
**Why It's Bad:** Unnecessary database load, slow response times  
**Status:** ⚠️ **FOUND** - No query caching implemented

**Example (BAD):**
```python
@users_bp.route("/profile", methods=["GET"])
@require_auth
async def get_profile():
    # ❌ Hits database every time, even though profile rarely changes
    async with get_async_db_session() as session:
        user = await session.get(User, g.user_id)
        return jsonify(user.to_dict()), 200
```

**How to Avoid:**
```python
from src.utils.redis_client import get_redis

@users_bp.route("/profile", methods=["GET"])
@require_auth
async def get_profile():
    redis_client = get_redis()
    cache_key = f"user_profile:{g.user_id}"
    
    # ✅ Try cache first
    cached = await redis_client.get_cache(cache_key)
    if cached:
        return jsonify(cached), 200
    
    # Cache miss -> query database
    async with get_async_db_session() as session:
        user = await session.get(User, g.user_id)
        profile_data = user.to_dict()
        
        # Store in cache (TTL: 5 minutes)
        await redis_client.set_cache(cache_key, profile_data, ttl=300)
        
        return jsonify(profile_data), 200
```

**Data to Cache:**
- User profiles (TTL: 5 minutes)
- Exercise templates (TTL: 1 hour)
- Achievement definitions (TTL: 24 hours)
- LLM responses for common queries (TTL: 2 hours)
- Progress calculations (TTL: 1 minute)

**Cache Invalidation:**
- Update profile -> invalidate `user_profile:{user_id}`
- Create exercise -> invalidate user exercise history cache
- Use cache tags or patterns for bulk invalidation

---

### AP-PERF-004: Synchronous LLM Calls Blocking Request Thread

**What:** LLM API calls block request thread for 3-5 seconds  
**Why It's Bad:** Poor UX, server thread starvation under load  
**Status:** ⚠️ **FOUND** - No streaming implemented

**Example (BAD):**
```python
@chat_bp.route("/send", methods=["POST"])
@require_auth
async def send_message():
    message = data["message"]
    # ❌ Blocks for 3-5 seconds waiting for LLM response
    response = await LLMService.generate_response(message)
    return jsonify({"response": response}), 200
```

**How to Avoid (Option 1: Streaming):**
```python
from quart import Response

@chat_bp.route("/send", methods=["POST"])
@require_auth
async def send_message_stream():
    message = data["message"]
    
    async def generate():
        # ✅ Stream LLM response token by token (SSE)
        async for token in LLMService.stream_response(message):
            yield f"data: {json.dumps({'token': token})}\n\n"
        yield "data: [DONE]\n\n"
    
    return Response(generate(), mimetype="text/event-stream")
```

**How to Avoid (Option 2: Background Jobs):**
```python
from celery import Celery

@chat_bp.route("/send", methods=["POST"])
@require_auth
async def send_message_async():
    message = data["message"]
    
    # ✅ Queue LLM call in background, return task ID
    task = generate_llm_response.delay(g.user_id, message)
    
    return jsonify({
        "task_id": task.id,
        "status": "processing"
    }), 202  # Accepted

# Frontend polls /task/{task_id} for result
```

---

## 4. Testing Anti-Patterns

### AP-TEST-001: Mocking Too Much

**What:** Mocking entire database or all external dependencies  
**Why It's Bad:** Tests pass but integration bugs still happen in production  
**Status:** ⚠️ **FOUND** - Some tests mock entire database

**Example (BAD):**
```python
def test_create_exercise():
    # ❌ Mocks everything - doesn't test real database interactions
    with patch('src.utils.database.get_async_db_session'):
        with patch('src.services.exercise_service.ExerciseService.create'):
            # Test passes but doesn't catch DB constraint violations!
```

**How to Avoid:**
```python
@pytest.mark.asyncio
async def test_create_exercise(test_db):
    # ✅ Use real test database (in-memory SQLite or dedicated test PostgreSQL)
    async with get_async_db_session() as session:
        exercise = await ExerciseService.create(
            user_id=1,
            title="Test Exercise",
            description="Test Description"
        )
        
        # Verify in database (real integration test)
        result = await session.get(Exercise, exercise.id)
        assert result.title == "Test Exercise"
```

**When to Mock:**
- ✅ External APIs (LLM, GitHub, email services)
- ✅ Time/date functions (for deterministic tests)
- ✅ Random number generators (for deterministic tests)
- ❌ Database (use test database instead)
- ❌ Redis (use test Redis instance or fakeredis)
- ❌ Internal services (test real integration)

---

### AP-TEST-002: No E2E Tests

**What:** Only unit tests, no full user journey tests  
**Why It's Bad:** Integration bugs, broken user flows not caught  
**Status:** ❌ **FOUND** - No E2E tests exist

**How to Avoid:**
```typescript
// ✅ Playwright E2E test
import { test, expect } from '@playwright/test';

test('user registration to first exercise flow', async ({ page }) => {
    // Navigate to registration
    await page.goto('http://localhost:3000/register');
    
    // Fill registration form
    await page.fill('input[name="email"]', 'test@example.com');
    await page.fill('input[name="password"]', 'SecureP@ss123');
    await page.click('button[type="submit"]');
    
    // Verify email verification page
    await expect(page).toHaveURL(/.*verify-email.*/);
    
    // Simulate email verification (backend API call)
    // Mock or use test email verification token
    await page.goto('http://localhost:3000/verify?token=test-token');
    
    // Complete onboarding
    await page.fill('select[name="language"]', 'Python');
    await page.fill('select[name="level"]', 'Intermediate');
    await page.click('button[type="submit"]');
    
    // Verify first exercise is shown
    await expect(page.locator('h1')).toContainText('Daily Exercise');
});
```

**Critical E2E Flows to Test:**
1. Registration → Email verification → Onboarding → First exercise
2. Login → Chat with tutor → Request hint
3. Exercise submission → Progress update → Achievement unlock
4. OAuth login (GitHub/Google)
5. Password reset flow
6. Profile update
7. Subscription upgrade (when payments implemented)

---

## 5. Frontend Anti-Patterns

### AP-UI-001: Props Drilling

**What:** Passing props through multiple component levels  
**Why It's Bad:** Hard to maintain, refactor, and understand  
**Status:** ⚠️ **FOUND** - Some components pass props 3+ levels deep

**Example (BAD):**
```typescript
// ❌ Props drilling
<Dashboard user={user}>
  <Sidebar user={user}>
    <UserProfile user={user}>
      <UserAvatar user={user} />  // 4 levels deep!
```

**How to Avoid:**
```typescript
// ✅ Use Redux for global state
// Store user in Redux store, access directly in any component

// UserAvatar.tsx
import { useAppSelector } from '../../store/hooks';

function UserAvatar() {
    const user = useAppSelector(state => state.auth.user);
    return <img src={user.avatar} alt={user.name} />;
}

// No props drilling needed!
```

---

### AP-UI-002: No Structured Logging in Frontend

**What:** Using console.log instead of structured logging  
**Why It's Bad:** Can't track errors in production, no context  
**Status:** ⚠️ **FOUND** - Frontend uses console.log

**Example (BAD):**
```typescript
console.log("User logged in");  // ❌ Lost in production
```

**How to Avoid:**
```typescript
// ✅ Use Sentry or LogRocket
import * as Sentry from "@sentry/react";

Sentry.captureMessage("User logged in", {
    level: "info",
    user: { id: user.id, email: user.email },
    tags: { environment: "production" }
});

// Errors automatically captured:
Sentry.captureException(error);
```

---

## 6. Deployment Anti-Patterns

### AP-DEPLOY-001: No Production Config Validation

**What:** Starting production server without validating environment variables  
**Why It's Bad:** Runtime failures, security issues (weak secrets)  
**Status:** ✅ **RESOLVED** - SEC-2 work stream added validation

**Current Implementation (GOOD):**
```python
@model_validator(mode='after')
def validate_production_config(self) -> 'Settings':
    if self.app_env != "production":
        return self
    
    # ✅ Validates in production:
    # - Secrets strength (32+ chars)
    # - No dev secret patterns ("changeme", "password", "test")
    # - HTTPS URLs required
    # - Database URL format (PostgreSQL)
    # - Redis URL format
    # - LLM API keys present
    
    if not self.frontend_url.startswith("https://"):
        raise ValueError("FRONTEND_URL must use HTTPS in production")
```

**Checklist for Production:**
- [ ] All required env vars present
- [ ] Secrets meet strength requirements
- [ ] No development secrets in production
- [ ] HTTPS enforced
- [ ] Database URL valid
- [ ] API keys present for third-party services

---

## 7. Code Review Checklist

Use this checklist during code reviews to catch anti-patterns:

### Security Review:
- [ ] No secrets committed to git
- [ ] All security decorators fully implemented (no placeholders)
- [ ] Input validation with Pydantic schemas
- [ ] Rate limiting on expensive endpoints
- [ ] Authentication required on protected routes
- [ ] Authorization checks for resource access
- [ ] SQL injection protection (parameterized queries)
- [ ] XSS protection (output encoding)
- [ ] CSRF protection (SameSite cookies + custom headers)

### Architecture Review:
- [ ] No God objects (service classes <300 lines)
- [ ] No magic numbers (constants extracted)
- [ ] Pagination on list endpoints
- [ ] Error codes for all error responses
- [ ] Async/await used correctly
- [ ] No blocking I/O in request handlers
- [ ] Proper separation of concerns (API → Service → Data)

### Performance Review:
- [ ] Database indexes on foreign keys and query fields
- [ ] No N+1 queries (eager loading configured)
- [ ] Query result caching for static data
- [ ] Pagination implemented (default limit, max limit)
- [ ] Streaming for long-running operations (LLM, file uploads)
- [ ] Connection pooling configured

### Testing Review:
- [ ] Tests written (TDD preferred)
- [ ] Integration tests for new features
- [ ] E2E test for critical user journeys
- [ ] Mock only external APIs (not database/internal services)
- [ ] Test coverage >80% for new code

### Documentation Review:
- [ ] Docstrings on public functions
- [ ] Type hints on function signatures
- [ ] README updated for new features
- [ ] OpenAPI schema updated
- [ ] Deployment docs updated if needed

---

## 8. Monitoring Anti-Pattern Detection

Set up automated checks to detect anti-patterns:

```bash
# Secrets in git
git ls-files | grep -E "\.env$|\.env\..+" | grep -v "\.env\.example"

# Magic numbers
rg '\b(60|300|3600|86400)\b' --type py | grep -v "test_" | grep -v "# TTL:"

# Missing pagination
rg "\.all\(\)" backend/src/api/ | grep "select("

# N+1 query risk
rg "for .* in .*\.scalars\(\)" backend/src/

# Missing rate limiting
rg "@.*_bp\.route" backend/src/api/ | xargs rg -l "@require_auth" | \
  xargs rg -L "@rate_limit"

# Console.log in frontend
rg "console\.(log|debug|info)" frontend/src/ | grep -v "\.test\."
```

---

## 9. Prevention Strategy

**Development Phase:**
1. Review this checklist before starting new features
2. Use code templates that follow best practices
3. Run automated checks in pre-commit hooks
4. Pair programming for critical features

**Code Review Phase:**
1. Reviewer uses section 7 checklist
2. Automated tools run (linters, security scanners)
3. At least one approval required
4. CI/CD tests must pass

**Deployment Phase:**
1. Config validation in staging
2. Security scan before production deployment
3. Load testing for performance-critical features
4. Rollback plan documented

---

**End of Checklist**  
**Last Updated:** 2025-12-06  
**Next Review:** After each major feature completion
