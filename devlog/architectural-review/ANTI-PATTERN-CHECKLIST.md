# Anti-Pattern Checklist
# LLM Coding Tutor Platform

**Review Date:** 2025-12-06
**Reviewer:** Autonomous Review Agent
**Codebase Stats:**
- Backend: ~9,639 lines of Python
- Frontend: ~7,439 lines of TypeScript/TSX
- Total Test Files: 24 (13 backend + 11 frontend)

---

## Critical Anti-Patterns (P0 - Fix Before Production)

### AP-CRIT-001: Hardcoded URLs in OAuth Flow
**Severity:** CRITICAL
**Category:** Security / Configuration
**Location:** `/home/llmtutor/llm_tutor/backend/src/api/auth.py`
**Lines:** 249, 282, 361, 377, 410, 487

**Issue:**
```python
# Line 249
redirect_uri = "http://localhost:5000/api/v1/auth/oauth/github/callback"

# Line 361
frontend_url = f"http://localhost:3000/auth/callback?access_token={tokens['access_token']}"
```

**Problems:**
1. Hardcoded localhost URLs will fail in production
2. Environment-specific configuration mixed into code
3. Impossible to deploy to multiple environments without code changes

**Impact:** OAuth authentication will completely fail in any non-local environment

**Recommended Fix:**
```python
from src.config import settings

redirect_uri = f"{settings.backend_url}/api/v1/auth/oauth/github/callback"
frontend_url = f"{settings.frontend_url}/auth/callback"
```

**Priority:** P0 - BLOCKER
**Estimated Effort:** 1 hour
**Related:** AP-SEC-001 (tokens in URL)

---

### AP-CRIT-002: Access Tokens Exposed in URL Parameters
**Severity:** CRITICAL
**Category:** Security
**Location:** `/home/llmtutor/llm_tutor/backend/src/api/auth.py`
**Lines:** 361, 487

**Issue:**
```python
frontend_url = f"http://localhost:3000/auth/callback?access_token={tokens['access_token']}"
return redirect(frontend_url, code=302)
```

**Problems:**
1. Tokens visible in browser history
2. Tokens leaked via Referer header
3. Tokens visible in proxy/server logs
4. CSRF vulnerability
5. Violates OAuth 2.0 security best practices (RFC 6749)

**Impact:** Token theft, session hijacking, complete account compromise

**Recommended Fix:**
Implement proper OAuth 2.0 Authorization Code Flow:
```python
# Backend: Return authorization code only
auth_code = generate_secure_code()
await redis.setex(f"oauth:code:{auth_code}", 300, json.dumps({
    "user_id": user.id,
    "provider": "github"
}))
frontend_url = f"{settings.frontend_url}/auth/callback?code={auth_code}"

# Frontend: Exchange code for token
POST /api/v1/auth/oauth/exchange
{
  "code": "..."
}
# Response sets httpOnly cookie with tokens
```

**Priority:** P0 - BLOCKER
**Estimated Effort:** 4 hours
**OWASP:** A01:2021 – Broken Access Control

---

### AP-CRIT-003: Database Connection Leak in Health Check
**Severity:** HIGH
**Category:** Resource Management
**Location:** `/home/llmtutor/llm_tutor/backend/src/app.py`
**Lines:** 166-180

**Issue:**
```python
# Line 169-171
db_manager = get_database()
with db_manager.sync_engine.connect() as conn:
    conn.execute(text("SELECT 1"))
```

**Problems:**
1. Creates connection from sync engine (should use async)
2. Application uses async everywhere else - inconsistent
3. Doubles connection pool requirements
4. `sync_engine` should not exist in async-only application

**Impact:** Resource exhaustion under load, inconsistent architecture

**Recommended Fix:**
```python
# Remove sync engine entirely
async def health_check():
    try:
        db_manager = get_database()
        async with db_manager.get_async_session() as session:
            await session.execute(text("SELECT 1"))
        health_status["database"] = "connected"
    except Exception as e:
        ...
```

**Priority:** P0 - CRITICAL
**Estimated Effort:** 2 hours
**Related:** AP-ARCH-004 (mixed sync/async)

---

### AP-CRIT-004: Missing Password Reset Session Invalidation
**Severity:** HIGH
**Category:** Security
**Location:** `/home/llmtutor/llm_tutor/backend/src/api/auth.py`
**Lines:** 715-720

**Issue:**
```python
# Line 720
# TODO: Invalidate all existing sessions for this user
# This would require iterating through Redis sessions...
```

**Problems:**
1. Attacker with stolen session remains logged in after victim resets password
2. Critical security feature marked as TODO
3. No user-level session tracking implemented

**Impact:** Security breach - compromised sessions remain valid indefinitely

**Recommended Fix:**
```python
# Add user session tracking
class AuthService:
    @staticmethod
    async def create_session(user_id: int, jti: str):
        await redis.sadd(f"user_sessions:{user_id}", jti)
        await redis.expire(f"user_sessions:{user_id}", 30 * 86400)

    @staticmethod
    async def invalidate_all_sessions(user_id: int):
        session_jtis = await redis.smembers(f"user_sessions:{user_id}")
        for jti in session_jtis:
            await redis.delete(f"session:{user_id}:{jti}")
        await redis.delete(f"user_sessions:{user_id}")

# In password reset:
await AuthService.invalidate_all_sessions(user.id)
```

**Priority:** P0 - BLOCKER
**Estimated Effort:** 3 hours
**OWASP:** A07:2021 – Identification and Authentication Failures

---

### AP-CRIT-005: Environment Variable Validation Too Late
**Severity:** MEDIUM-HIGH
**Category:** Configuration / Reliability
**Location:** `/home/llmtutor/llm_tutor/backend/src/config.py`
**Lines:** 104-127

**Issue:**
```python
def get_settings() -> Settings:
    settings = Settings()
    # Validation happens after instantiation
    critical_fields = {...}
    # ...
```

**Problems:**
1. Pydantic validation happens on field access, not construction
2. Application may start with invalid config
3. Errors discovered during runtime, not startup
4. No validation of SECRET_KEY strength or JWT_SECRET_KEY entropy

**Impact:** Application fails after startup in production

**Recommended Fix:**
```python
from pydantic import field_validator, SecretStr

class Settings(BaseSettings):
    secret_key: SecretStr = Field(..., min_length=32, env="SECRET_KEY")
    jwt_secret_key: SecretStr = Field(..., min_length=32, env="JWT_SECRET_KEY")

    @field_validator('secret_key', 'jwt_secret_key')
    def validate_secret_strength(cls, v):
        if len(str(v)) < 32:
            raise ValueError('Secret keys must be at least 32 characters')
        return v

    model_config = {
        'validate_assignment': True,
        'extra': 'forbid',  # Fail on unknown env vars
    }

# Module level - fails fast on import
settings = Settings()
```

**Priority:** P1 - HIGH
**Estimated Effort:** 2 hours

---

## High-Priority Anti-Patterns (P1 - Fix Before Launch)

### AP-SEC-001: Insecure Token Storage (Frontend)
**Severity:** HIGH
**Category:** Security
**Location:** `/home/llmtutor/llm_tutor/frontend/src/services/api.ts`
**Lines:** ~16

**Issue:**
```typescript
const token = localStorage.getItem('authToken');
```

**Problems:**
1. `localStorage` vulnerable to XSS attacks
2. Tokens persist across browser restarts
3. No expiration handling on client
4. Accessible to any JavaScript on the page

**Impact:** Token theft via XSS, persistent exposure

**Recommended Fix:**
Option 1 (Best): httpOnly cookies
```typescript
// Backend sets httpOnly cookie
response.set_cookie(
    'access_token',
    token,
    httponly=True,
    secure=True,
    samesite='strict',
    max_age=86400
)

// Frontend: No token storage needed, browser handles it
axios.defaults.withCredentials = true;
```

Option 2: Memory-only storage
```typescript
// Store in React context/Redux, never localStorage
const AuthContext = createContext<{token: string | null}>({token: null});
```

**Priority:** P1 - HIGH
**Estimated Effort:** 3 hours
**OWASP:** A03:2021 – Injection (XSS)

---

### AP-SEC-002: Email Enumeration via Registration
**Severity:** MEDIUM
**Category:** Security / Privacy
**Location:** `/home/llmtutor/llm_tutor/backend/src/api/auth.py`
**Lines:** 71-79

**Issue:**
```python
if existing_user:
    raise APIError("User with this email already exists", status_code=409)
```

**Problems:**
1. Attackers can enumerate valid email addresses
2. Violates user privacy
3. Enables targeted phishing attacks
4. Inconsistent with password reset (which correctly prevents enumeration)

**Impact:** Privacy violation, reconnaissance for attacks

**Recommended Fix:**
```python
# Always return same response
if existing_user:
    # Send email: "Someone tried to register with your email"
    logger.info("Duplicate registration attempt", extra={"email_hash": hash(email)})
    # Delay response to match successful registration timing
    await asyncio.sleep(random.uniform(0.5, 1.0))

# Return success regardless
return jsonify({
    "message": "Registration successful. Please check your email to verify your account.",
    "success": True
}), 201
```

**Priority:** P1 - MEDIUM
**Estimated Effort:** 2 hours
**CWE:** CWE-204: Observable Response Discrepancy

---

### AP-SEC-003: CORS Configuration Too Permissive
**Severity:** MEDIUM
**Category:** Security
**Location:** `/home/llmtutor/llm_tutor/backend/src/app.py`
**Lines:** 70-77

**Issue:**
```python
allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"]
```

**Problems:**
1. All HTTP methods allowed globally
2. PATCH and DELETE allowed but not used
3. No route-specific CORS configuration
4. Missing `max_age` for preflight caching

**Impact:** Potential CSRF, unnecessary attack surface

**Recommended Fix:**
```python
# Global: Only safe methods
app = cors(
    app,
    allow_origin=settings.cors_origins,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
    allow_credentials=True,
    max_age=3600,  # Cache preflight for 1 hour
)

# Per-route: Add specific methods as needed
@auth_bp.route("/users/<int:user_id>", methods=["DELETE"])
@cors(allow_methods=["DELETE"])
async def delete_user(user_id: int):
    ...
```

**Priority:** P1 - MEDIUM
**Estimated Effort:** 1 hour

---

### AP-DATA-001: Missing Database Indexes
**Severity:** MEDIUM-HIGH
**Category:** Performance
**Location:** `/home/llmtutor/llm_tutor/backend/src/models/user.py`
**Lines:** Various

**Issue:**
Only `email`, `github_id`, `google_id`, `last_exercise_date`, and `created_at` have indexes.

**Missing Indexes:**
1. `users.role` - Filtered in admin queries
2. `users.is_active` - Filtered everywhere
3. `users.onboarding_completed` - Filtered in dashboard
4. `exercises.difficulty` - Used in adaptive difficulty queries
5. `exercises.language` - Used in exercise generation
6. `user_exercises.status` - Used in progress tracking
7. `user_exercises.created_at` - Used in streak calculations
8. `conversations.user_id` - Foreign key, frequently joined
9. Composite index: `(user_id, created_at)` on user_exercises

**Impact:** Slow queries at scale, full table scans

**Recommended Fix:**
```python
# In User model
is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
role: Mapped[UserRole] = mapped_column(
    SQLEnum(UserRole), default=UserRole.STUDENT, nullable=False, index=True
)

# In Exercise model
difficulty: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
language: Mapped[str] = mapped_column(String(50), nullable=False, index=True)

# Composite indexes via Index()
__table_args__ = (
    Index('ix_user_exercises_user_created', 'user_id', 'created_at'),
    Index('ix_user_exercises_status', 'status'),
)
```

**Priority:** P1 - HIGH
**Estimated Effort:** 2 hours
**Impact at Scale:** Query time 100x+ slower without indexes

---

### AP-DATA-002: No Soft Deletes or Audit Trail
**Severity:** MEDIUM
**Category:** Data Integrity / Compliance
**Location:** All models

**Issue:**
No tracking of:
1. Who modified records (created_by, updated_by)
2. When records were deleted (deleted_at)
3. Audit history for compliance (GDPR Article 30)

**Problems:**
1. Permanent data loss on delete
2. No accountability for data changes
3. GDPR compliance impossible
4. Cannot recover from accidental deletions

**Impact:** Data loss, compliance violations, audit failures

**Recommended Fix:**
```python
# Create AuditMixin
class AuditMixin:
    created_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    updated_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None

# Apply to all models
class User(Base, AuditMixin):
    ...

# Automatic query filtering
@event.listens_for(Session, 'do_orm_execute')
def _add_filtering_criteria(execute_state):
    if not execute_state.is_select:
        return
    # Filter out soft-deleted records by default
    execute_state.statement = execute_state.statement.filter_by(deleted_at=None)
```

**Priority:** P1 - HIGH
**Estimated Effort:** 6 hours (migration required)
**Compliance:** GDPR Article 30 (Records of Processing)

---

## Medium-Priority Anti-Patterns (P2 - Improve Quality)

### AP-ARCH-001: Service Layer Uses Static Methods
**Severity:** MEDIUM
**Category:** Architecture / Testability
**Location:** Multiple services
- `/home/llmtutor/llm_tutor/backend/src/services/auth_service.py`
- `/home/llmtutor/llm_tutor/backend/src/services/profile_service.py`
- `/home/llmtutor/llm_tutor/backend/src/services/exercise_service.py`

**Issue:**
```python
class AuthService:
    @staticmethod
    async def generate_token_pair(...):
        ...
```

**Problems:**
1. Not a true service pattern - just namespacing functions
2. Cannot inject dependencies (tight coupling)
3. Difficult to mock in tests
4. No state management or lifecycle
5. Prevents proper dependency injection

**Impact:** Poor testability, tight coupling, difficult to refactor

**Recommended Fix:**
```python
class AuthService:
    def __init__(
        self,
        redis_manager: RedisManager,
        config: Settings,
        logger: Logger,
    ):
        self.redis = redis_manager
        self.config = config
        self.logger = logger

    async def generate_token_pair(self, user_id: int, ...) -> Dict[str, str]:
        # Now can mock dependencies
        ...

# In dependency injection container
def get_auth_service() -> AuthService:
    return AuthService(
        redis_manager=get_redis(),
        config=settings,
        logger=get_logger(__name__),
    )

# In routes
@auth_bp.route("/login")
async def login():
    auth_service = get_auth_service()
    tokens = await auth_service.generate_token_pair(...)
```

**Priority:** P2 - MEDIUM
**Estimated Effort:** 8 hours (affects all services)
**Benefits:** Testability, decoupling, maintainability

---

### AP-ARCH-002: No Repository Pattern
**Severity:** MEDIUM
**Category:** Architecture
**Location:** Direct SQLAlchemy queries in route handlers

**Issue:**
```python
# In routes/services - direct database access
result = await session.execute(
    select(User).where(User.email == email)
)
user = result.scalar_one_or_none()
```

**Problems:**
1. Database logic scattered across routes and services
2. Difficult to test without database
3. Query logic duplicated
4. Cannot optimize queries centrally (eager loading, caching)

**Impact:** Code duplication, poor testability, difficult optimization

**Recommended Fix:**
```python
class UserRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def find_by_email(self, email: str) -> Optional[User]:
        result = await self.session.execute(
            select(User)
            .where(User.email == email)
            .options(joinedload(User.achievements))  # Centralized optimization
        )
        return result.scalar_one_or_none()

    async def find_active_users(self) -> List[User]:
        result = await self.session.execute(
            select(User).where(User.is_active == True)
        )
        return result.scalars().all()

# In service
class AuthService:
    def __init__(self, user_repo: UserRepository, ...):
        self.user_repo = user_repo

    async def login(self, email: str, ...):
        user = await self.user_repo.find_by_email(email)
```

**Priority:** P2 - MEDIUM
**Estimated Effort:** 12 hours
**Benefits:** Testability, maintainability, centralized optimization

---

### AP-ARCH-003: Global Singletons Without Thread Safety
**Severity:** MEDIUM
**Category:** Concurrency
**Location:**
- `/home/llmtutor/llm_tutor/backend/src/utils/database.py:202`
- `/home/llmtutor/llm_tutor/backend/src/utils/redis_client.py:293`

**Issue:**
```python
_db_manager = None

def init_database(...):
    global _db_manager
    _db_manager = DatabaseManager(...)  # Race condition!
    return _db_manager
```

**Problems:**
1. No locking on initialization
2. Multiple workers can create multiple instances
3. Race condition in concurrent startup
4. Violates singleton guarantee

**Impact:** Multiple database pools, resource waste, unpredictable behavior

**Recommended Fix:**
```python
import threading

_db_manager = None
_db_lock = threading.Lock()

def init_database(...):
    global _db_manager
    if _db_manager is not None:
        return _db_manager

    with _db_lock:
        # Double-checked locking
        if _db_manager is None:
            _db_manager = DatabaseManager(...)
    return _db_manager
```

**Priority:** P2 - MEDIUM
**Estimated Effort:** 1 hour

---

### AP-ARCH-004: Mixed Sync and Async Database Access
**Severity:** MEDIUM-HIGH
**Category:** Architecture / Performance
**Location:** `/home/llmtutor/llm_tutor/backend/src/utils/database.py`

**Issue:**
```python
class DatabaseManager:
    def __init__(self, ...):
        self.sync_engine = create_engine(...)
        self.async_engine = create_async_engine(...)
        # Doubles connection pool requirements!
```

**Problems:**
1. Application is async (Quart) but maintains sync engine
2. Doubles connection pool size and memory
3. Sync engine only used in health check and Alembic
4. Inconsistent patterns throughout codebase

**Impact:** Resource waste, complexity, potential deadlocks

**Recommended Fix:**
```python
class DatabaseManager:
    def __init__(self, ...):
        # ONLY async engine
        self.async_engine = create_async_engine(...)

    # For Alembic only
    def get_sync_engine_for_migration(self):
        return create_engine(database_url.replace('+asyncpg', '+psycopg2'))

# Health check - use async
async def health_check():
    async with db_manager.get_async_session() as session:
        await session.execute(text("SELECT 1"))
```

**Priority:** P1 - HIGH
**Estimated Effort:** 4 hours
**Benefits:** 50% reduction in connection pool size

---

### AP-TEST-001: Heavy Mocking in Unit Tests
**Severity:** MEDIUM
**Category:** Testing
**Location:** Test files throughout

**Issue:**
Project instructions state: "prioritize integration testing over heavily mocked unit tests" but implementation appears to violate this.

**Problems:**
1. Unit tests with heavy mocking don't catch integration bugs
2. Tests pass but real interactions fail
3. Fragile tests break on refactoring
4. False confidence in code quality

**Impact:** Integration bugs slip through, low test value

**Recommended Fix:**
```python
# BAD: Heavy mocking
@pytest.mark.asyncio
async def test_create_user(mocker):
    mock_session = mocker.Mock()
    mock_user = mocker.Mock()
    mock_session.execute.return_value.scalar_one_or_none.return_value = None
    # Tests mock, not real code!

# GOOD: Integration test
@pytest.mark.asyncio
async def test_create_user(test_db):
    """Test with real database (Docker container)"""
    async with test_db.session() as session:
        user = User(email="test@example.com", name="Test")
        session.add(user)
        await session.commit()

        # Query real DB
        result = await session.execute(
            select(User).where(User.email == "test@example.com")
        )
        assert result.scalar_one().name == "Test"
```

**Priority:** P2 - MEDIUM
**Estimated Effort:** 16 hours (rewrite tests)
**Benefits:** Catch real bugs, reduce maintenance

---

### AP-CODE-001: Magic Numbers Throughout Codebase
**Severity:** LOW-MEDIUM
**Category:** Code Quality
**Location:** Multiple files

**Issue:**
```python
expiration=86400  # What is this?
bcrypt_rounds=12  # Why 12?
pool_size=20  # Based on what?
max_connections=50  # Arbitrary?
```

**Problems:**
1. Meaning not obvious
2. Difficult to maintain
3. Easy to introduce bugs when changing
4. No documentation of rationale

**Impact:** Reduced maintainability, potential bugs

**Recommended Fix:**
```python
class TimeConstants:
    SECONDS_PER_MINUTE = 60
    SECONDS_PER_HOUR = 3600
    SECONDS_PER_DAY = 86400
    EMAIL_VERIFICATION_TTL = SECONDS_PER_DAY
    ACCESS_TOKEN_TTL = SECONDS_PER_DAY
    REFRESH_TOKEN_TTL = 30 * SECONDS_PER_DAY

class SecurityConstants:
    BCRYPT_ROUNDS = 12  # NIST recommends 10-12 for 2023
    PASSWORD_MIN_LENGTH = 12
    JWT_ALGORITHM = "HS256"

class DatabaseConstants:
    # Based on: workers * threads * 2 + overhead
    # 4 workers * 4 threads * 2 + 4 = 36
    CONNECTION_POOL_SIZE = 36
    CONNECTION_MAX_OVERFLOW = 10
```

**Priority:** P2 - MEDIUM
**Estimated Effort:** 4 hours

---

### AP-CODE-002: Inconsistent Naming Conventions
**Severity:** LOW
**Category:** Code Quality
**Location:** Throughout

**Issue:**
- `get_user` vs `find_user`
- `create_user` vs `register_user`
- `update` vs `modify`

**Problems:**
1. Confusion about method behavior
2. Difficult to discover APIs
3. Increases cognitive load

**Impact:** Developer productivity, onboarding friction

**Recommended Fix:**
Establish and document conventions:
```python
# Naming Convention Standard:
# - get_*() - Retrieve or raise exception (guaranteed return)
# - find_*() - Retrieve or return None (optional return)
# - create_*() - Insert new record
# - update_*() - Modify existing record
# - delete_*() - Remove record (soft delete if applicable)
# - list_*() - Return multiple records
# - count_*() - Return count of records
```

**Priority:** P2 - LOW
**Estimated Effort:** 8 hours (rename + update calls)

---

### AP-CODE-003: No Error Context in Logging
**Severity:** MEDIUM
**Category:** Observability
**Location:** Throughout backend

**Issue:**
```python
logger.error("Failed to verify token", exc_info=True)
```

**Problems:**
1. No request context (path, method, IP)
2. No user context (user_id, email_hash)
3. Difficult to debug in production
4. Cannot correlate errors across requests

**Impact:** Slow debugging, poor observability

**Recommended Fix:**
```python
# Add structured logging context
logger.error(
    "Failed to verify token",
    exc_info=True,
    extra={
        "user_id": user_id,
        "token_jti": token[:10],  # First 10 chars only
        "request_id": request_id,
        "request_path": request.path,
        "request_method": request.method,
        "user_agent": request.headers.get("User-Agent"),
        "ip_address": request.remote_addr,
    }
)

# Add request ID middleware
@app.before_request
async def add_request_id():
    g.request_id = str(uuid.uuid4())
```

**Priority:** P2 - MEDIUM
**Estimated Effort:** 6 hours

---

## Low-Priority Anti-Patterns (P3 - Nice to Have)

### AP-FRONTEND-001: No Code Splitting
**Severity:** LOW
**Category:** Performance
**Location:** `/home/llmtutor/llm_tutor/frontend/src/routes.tsx`

**Issue:**
All routes imported synchronously:
```typescript
import DashboardPage from './pages/DashboardPage';
import ProfilePage from './pages/ProfilePage';
// All loaded upfront!
```

**Impact:** Larger initial bundle, slower page load

**Recommended Fix:**
```typescript
import { lazy } from 'react';

const DashboardPage = lazy(() => import('./pages/DashboardPage'));
const ProfilePage = lazy(() => import('./pages/ProfilePage'));
const ChatPage = lazy(() => import('./pages/ChatPage'));

// Wrap in Suspense
<Suspense fallback={<LoadingSpinner />}>
  <Routes>
    <Route path="/dashboard" element={<DashboardPage />} />
  </Routes>
</Suspense>
```

**Priority:** P3 - LOW
**Estimated Effort:** 2 hours
**Benefit:** 30-50% smaller initial bundle

---

### AP-FRONTEND-002: No Error Boundaries
**Severity:** MEDIUM
**Category:** Reliability
**Location:** Frontend - missing entirely

**Issue:**
No React error boundaries implemented

**Impact:** White screen of death on errors, poor UX

**Recommended Fix:**
```typescript
class ErrorBoundary extends React.Component {
  state = { hasError: false, error: null };

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    logErrorToService(error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return <ErrorFallback error={this.state.error} />;
    }
    return this.props.children;
  }
}

// Wrap app
<ErrorBoundary>
  <App />
</ErrorBoundary>
```

**Priority:** P2 - MEDIUM
**Estimated Effort:** 3 hours

---

### AP-OBS-001: No Distributed Tracing
**Severity:** MEDIUM
**Category:** Observability
**Location:** Missing entirely

**Issue:**
No OpenTelemetry or APM integration

**Impact:** Cannot trace requests across services, slow debugging

**Recommended Fix:**
```python
from opentelemetry import trace
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor

tracer = trace.get_tracer(__name__)

@tracer.start_as_current_span("user.login")
async def login():
    with tracer.start_as_current_span("database.query"):
        user = await user_repo.find_by_email(email)
    with tracer.start_as_current_span("jwt.generate"):
        tokens = await auth_service.generate_tokens(user)
    return tokens

# Auto-instrument
SQLAlchemyInstrumentor().instrument(engine=db_engine)
RedisInstrumentor().instrument()
```

**Priority:** P2 - MEDIUM
**Estimated Effort:** 6 hours
**Benefit:** Massive debugging speedup

---

### AP-OBS-002: No Metrics Collection
**Severity:** MEDIUM
**Category:** Observability
**Location:** Missing entirely

**Issue:**
No Prometheus/StatsD metrics

**Impact:** Cannot monitor performance trends, capacity planning impossible

**Recommended Fix:**
```python
from prometheus_client import Counter, Histogram, Gauge

# Define metrics
http_requests_total = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status']
)

http_request_duration = Histogram(
    'http_request_duration_seconds',
    'HTTP request duration',
    ['method', 'endpoint']
)

# Instrument
@app.before_request
async def before_request():
    g.start_time = time.time()

@app.after_request
async def after_request(response):
    duration = time.time() - g.start_time
    http_request_duration.labels(
        method=request.method,
        endpoint=request.endpoint
    ).observe(duration)
    http_requests_total.labels(
        method=request.method,
        endpoint=request.endpoint,
        status=response.status_code
    ).inc()
    return response

# Expose metrics
@app.route("/metrics")
async def metrics():
    return generate_latest()
```

**Priority:** P2 - MEDIUM
**Estimated Effort:** 4 hours

---

## Summary Statistics

**Total Anti-Patterns Identified:** 21

**By Severity:**
- Critical (P0): 5
- High (P1): 6
- Medium (P2): 7
- Low (P3): 3

**By Category:**
- Security: 7
- Architecture: 5
- Data/Database: 3
- Code Quality: 3
- Observability: 2
- Testing: 1

**Total Estimated Effort:** ~110 hours
- Critical fixes: ~12 hours
- High priority: ~23 hours
- Medium priority: ~61 hours
- Low priority: ~14 hours

**Recommended Phasing:**
1. **Week 1:** Critical issues (AP-CRIT-001 through AP-CRIT-005) - 12 hours
2. **Week 2:** Security issues (AP-SEC-001 through AP-SEC-003) + Data integrity (AP-DATA-001, AP-DATA-002) - 16 hours
3. **Week 3:** Architecture refactoring (AP-ARCH-001 through AP-ARCH-004) - 25 hours
4. **Week 4:** Testing improvements (AP-TEST-001) + Code quality (AP-CODE-001 through AP-CODE-003) - 28 hours
5. **Week 5:** Observability (AP-OBS-001, AP-OBS-002) + Frontend (AP-FRONTEND-001, AP-FRONTEND-002) - 15 hours

---

**Document Version:** 1.0
**Last Updated:** 2025-12-06
**Maintainer:** Platform Architecture Team
