# Anti-Patterns Checklist
# LLM Coding Tutor Platform

## Document Version: 1.0
## Date: 2025-12-06
## Status: Active Review Findings

---

## Purpose

This document catalogs anti-patterns and code smells identified during architectural review of the LLM Coding Tutor Platform. Each anti-pattern includes specific examples from the codebase, impact assessment, and recommended fixes.

---

## Critical Anti-Patterns

### 1. Multiple Database Session Management Patterns

**Severity**: HIGH
**Category**: Architecture / Data Access
**Files Affected**:
- `/home/llmtutor/llm_tutor/backend/src/utils/database.py`
- `/home/llmtutor/llm_tutor/backend/src/models/base.py`

**Description**:
The codebase has TWO separate database modules with conflicting session management patterns:
1. `src/models/base.py` - Uses `get_db_session()` context manager
2. `src/utils/database.py` - Uses `get_async_db_session()` context manager

**Specific Examples**:
```python
# Pattern 1: In src/models/base.py
@asynccontextmanager
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    if _async_session_factory is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    async with _async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise

# Pattern 2: In src/utils/database.py
@asynccontextmanager
async def get_async_db_session():
    db_manager = get_database()
    async with db_manager.get_async_session() as session:
        yield session
```

**Impact**:
- Developers must choose between two different import paths
- Risk of using wrong session factory in different parts of codebase
- Duplicate initialization logic leads to maintenance burden
- Potential for connection pool exhaustion if both are initialized

**Recommended Fix**:
1. Consolidate to SINGLE database module (`src/utils/database.py`)
2. Remove duplicate session management from `src/models/base.py`
3. Update all imports to use unified pattern
4. Add deprecation warnings if gradual migration needed

---

### 2. Inconsistent Import Aliasing for Database Sessions

**Severity**: MEDIUM
**Category**: Code Consistency
**Files Affected**:
- `/home/llmtutor/llm_tutor/backend/src/api/auth.py` (line 18)
- Various API endpoints

**Description**:
Database session imports use inconsistent aliasing:
```python
from src.utils.database import get_async_db_session as get_session
```

**Impact**:
- Reduced code readability (unclear what `get_session` returns)
- Makes grep/search for session usage difficult
- New developers confused about async vs sync sessions

**Recommended Fix**:
```python
# Use consistent, descriptive names
from src.utils.database import get_async_db_session

# In code:
async with get_async_db_session() as session:
    # Clear that this is async
```

---

### 3. Mixed Configuration Management Approaches

**Severity**: MEDIUM
**Category**: Configuration / Settings
**Files Affected**:
- `/home/llmtutor/llm_tutor/backend/src/config.py`
- `/home/llmtutor/llm_tutor/backend/src/app.py`

**Description**:
Configuration mixing Pydantic Settings with direct environment variable access:

```python
# In config.py - Good: Using Pydantic Settings
class Settings(BaseSettings):
    secret_key: str = Field(..., env="SECRET_KEY")

# But then in config.py:
settings = get_settings()  # Global singleton

# In app.py - Redundant:
from .config import settings
# Settings accessed as global singleton instead of dependency injection
```

**Impact**:
- Testing becomes difficult (global state)
- Cannot easily override settings for different test scenarios
- Circular dependency risks

**Recommended Fix**:
1. Use dependency injection for settings
2. Avoid global `settings` singleton
3. Pass settings explicitly where needed or use Quart's app.config

---

### 4. Overly Permissive Exception Handling

**Severity**: MEDIUM
**Category**: Error Handling
**Files Affected**:
- `/home/llmtutor/llm_tutor/backend/src/app.py` (lines 134-148)
- `/home/llmtutor/llm_tutor/backend/src/services/auth_service.py` (multiple locations)

**Description**:
Bare `except Exception` catches that mask specific errors:

```python
@app.errorhandler(Exception)
async def handle_exception(error):
    """Handle uncaught exceptions."""
    logger.error("Uncaught exception", exc_info=True)
    return jsonify({
        "error": "Internal Server Error",
        "message": "An unexpected error occurred",
        "status": 500,
    }), 500
```

**Impact**:
- Masks `KeyboardInterrupt`, `SystemExit`, and other critical exceptions
- Makes debugging harder (generic error messages)
- Potential to catch errors that should propagate

**Recommended Fix**:
```python
# Be specific about what to catch
@app.errorhandler(APIError)
async def handle_api_error(error):
    # Handle known API errors

@app.errorhandler(Exception)
async def handle_exception(error):
    # Only catch if not a system exception
    if isinstance(error, (KeyboardInterrupt, SystemExit)):
        raise
    # Log and handle
```

---

### 5. Password Validation in Service Layer Without Pre-Validation

**Severity**: MEDIUM
**Category**: Security / Input Validation
**Files Affected**:
- `/home/llmtutor/llm_tutor/backend/src/services/auth_service.py` (lines 86-104)

**Description**:
Password hashing function validates and hashes in one step:

```python
@staticmethod
def hash_password(password: str) -> str:
    """Hash password using bcrypt."""
    AuthService.validate_password(password)  # Validates INSIDE hash function
    salt = bcrypt.gensalt(rounds=settings.bcrypt_rounds)
    hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
    return hashed.decode("utf-8")
```

**Impact**:
- Violates Single Responsibility Principle
- Makes testing harder (cannot test validation separate from hashing)
- If hashing is expensive and validation fails, wasted CPU cycles

**Recommended Fix**:
```python
# Separate validation from hashing
@staticmethod
def validate_password(password: str) -> bool:
    # Just validation logic

@staticmethod
def hash_password(password: str) -> str:
    # Assume pre-validated, just hash
    # Or add assertion for safety
```

---

### 6. Database Session Commit Inside Context Manager

**Severity**: LOW
**Category**: Data Access / Transaction Management
**Files Affected**:
- `/home/llmtutor/llm_tutor/backend/src/models/base.py` (lines 94-118)
- `/home/llmtutor/llm_tutor/backend/src/utils/database.py` (lines 144-168)

**Description**:
Session context managers auto-commit on exit:

```python
@asynccontextmanager
async def get_db_session():
    async with _async_session_factory() as session:
        try:
            yield session
            await session.commit()  # Auto-commits
        except Exception:
            await session.rollback()
            raise
```

**Impact**:
- Removes explicit transaction control from calling code
- Cannot batch multiple operations in single transaction
- Makes complex transaction logic harder

**Recommended Fix**:
```python
# Let caller control commits
@asynccontextmanager
async def get_db_session(auto_commit: bool = True):
    async with _async_session_factory() as session:
        try:
            yield session
            if auto_commit:
                await session.commit()
        except Exception:
            await session.rollback()
            raise
```

---

### 7. Security Token Email Enumeration Vulnerability

**Severity**: MEDIUM
**Category**: Security
**Files Affected**:
- `/home/llmtutor/llm_tutor/backend/src/api/auth.py` (lines 24-86, 627-679)

**Description**:
Registration endpoint attempts to prevent email enumeration but still reveals timing differences:

```python
# Check if user already exists
existing_user = result.scalar_one_or_none()

if existing_user:
    # Returns success without sending email
    return jsonify({
        "message": "Registration successful. Please check your email...",
    }), 201

# Create new user
# ... sends actual email verification
```

**Impact**:
- Attackers can use timing attacks to enumerate valid emails
- Different code paths = different response times

**Recommended Fix**:
1. Always send email (even if user exists, send "already registered" email)
2. Use constant-time comparison where possible
3. Add random delay to normalize response times

---

### 8. Hardcoded Quart Configuration Patch

**Severity**: HIGH
**Category**: Framework / Stability
**Files Affected**:
- `/home/llmtutor/llm_tutor/backend/src/app.py` (lines 42-56)

**Description**:
Monkey-patches Flask Config class to work around Quart initialization issue:

```python
# Workaround: Set Flask default config for PROVIDE_AUTOMATIC_OPTIONS
from flask.config import Config as FlaskConfig
original_init = FlaskConfig.__init__
def patched_init(self, *args, **kwargs):
    original_init(self, *args, **kwargs)
    self.setdefault("PROVIDE_AUTOMATIC_OPTIONS", True)

FlaskConfig.__init__ = patched_init
```

**Impact**:
- CRITICAL: Modifying framework internals is fragile
- May break on Quart/Flask updates
- Unexpected behavior in other parts of application
- Hard to debug issues caused by the patch

**Recommended Fix**:
1. File issue with Quart project
2. Set config value after app creation instead of monkey-patching
3. Document why this is needed
4. Add version guards to prevent breaking on updates

---

### 9. Missing Database Connection Pool Monitoring

**Severity**: MEDIUM
**Category**: Performance / Observability
**Files Affected**:
- `/home/llmtutor/llm_tutor/backend/src/utils/database.py`

**Description**:
Database connection pool configured but no monitoring for pool exhaustion:

```python
self._sync_engine = create_engine(
    self.database_url,
    poolclass=QueuePool,
    pool_size=20,
    max_overflow=10,
    pool_pre_ping=True,
    echo=self.echo,
)
```

**Impact**:
- No visibility into connection pool utilization
- Cannot detect pool exhaustion before failures occur
- No metrics for capacity planning

**Recommended Fix**:
```python
# Add pool monitoring
from sqlalchemy import event

@event.listens_for(engine, "connect")
def receive_connect(dbapi_conn, connection_record):
    logger.debug("Database connection acquired")
    # Log pool stats
    pool = engine.pool
    logger.info("Pool stats", extra={
        "size": pool.size(),
        "checked_in": pool.checkedin(),
        "checked_out": pool.checkedout(),
        "overflow": pool.overflow(),
    })
```

---

### 10. Inconsistent Async/Await Patterns

**Severity**: LOW
**Category**: Code Quality
**Files Affected**:
- Various API endpoints

**Description**:
Some async functions don't await all async operations consistently.

**Example**:
```python
# Missing await for background task
async def some_endpoint():
    # Should this be awaited?
    send_email(user.email, token)  # If async, needs await
    return response
```

**Impact**:
- Potential for operations to not complete
- Race conditions
- Unclear function contracts

**Recommended Fix**:
1. Use type hints to indicate async: `async def foo() -> Awaitable[...]`
2. Enable mypy strict mode
3. Lint for missing awaits

---

## Medium Priority Anti-Patterns

### 11. JWT Token Secret Key Reuse

**Severity**: MEDIUM
**Category**: Security
**Files Affected**:
- `/home/llmtutor/llm_tutor/backend/src/config.py` (lines 18, 34)

**Description**:
Both `secret_key` and `jwt_secret_key` are separate fields, but they serve similar purposes:

```python
secret_key: str = Field(..., env="SECRET_KEY")
jwt_secret_key: str = Field(..., env="JWT_SECRET_KEY")
```

**Impact**:
- If developers set both to same value, key compromise affects more systems
- Unclear which key is used where

**Recommended Fix**:
- Document that these MUST be different values
- Add validation to ensure they're not identical
- Consider using derived keys

---

### 12. Missing API Versioning in Routes

**Severity**: LOW
**Category**: API Design
**Files Affected**:
- Blueprint registration

**Description**:
While code mentions `/api/v1`, actual blueprint registration may not enforce versioning.

**Impact**:
- Breaking changes harder to manage
- Cannot maintain multiple API versions

**Recommended Fix**:
```python
# Enforce version prefix
api_v1 = Blueprint('api_v1', __name__, url_prefix='/api/v1')
```

---

### 13. No Request ID Correlation

**Severity**: MEDIUM
**Category**: Observability / Logging
**Files Affected**:
- Middleware and logging

**Description**:
Logs don't include request correlation IDs to trace requests across services.

**Impact**:
- Difficult to debug multi-step operations
- Cannot correlate logs for single user request

**Recommended Fix**:
```python
# Add request ID middleware
import uuid

@app.before_request
async def add_request_id():
    g.request_id = request.headers.get('X-Request-ID', str(uuid.uuid4()))

# Include in all logs
logger.info("Request processed", extra={"request_id": g.request_id})
```

---

### 14. OAuth State Storage Without TTL

**Severity**: MEDIUM
**Category**: Security
**Files Affected**:
- OAuth implementation

**Description**:
OAuth state tokens stored in Redis may not have appropriate TTL.

**Impact**:
- Stale state tokens accumulate
- Potential security risk if state reused

**Recommended Fix**:
- Set short TTL (5 minutes) on OAuth state
- Clean up after use

---

### 15. Missing Database Migration Testing

**Severity**: MEDIUM
**Category**: Database / DevOps
**Files Affected**:
- Alembic migrations

**Description**:
No automated tests for database migrations (up/down).

**Impact**:
- Migration failures discovered in production
- Data loss risk on rollback

**Recommended Fix**:
```python
# Add migration tests
def test_migration_up():
    # Apply migration
    # Verify schema changes

def test_migration_down():
    # Rollback migration
    # Verify schema restored
```

---

## Low Priority Anti-Patterns

### 16. Magic Numbers in Configuration

**Severity**: LOW
**Category**: Code Quality
**Files Affected**:
- Various configuration values

**Description**:
Hardcoded values without explanation:
```python
await redis_manager.set_cache(key, data, 86400)  # What is 86400?
```

**Recommended Fix**:
```python
ONE_DAY_SECONDS = 86400
await redis_manager.set_cache(key, data, ONE_DAY_SECONDS)
```

---

### 17. Inconsistent Error Response Format

**Severity**: LOW
**Category**: API Design
**Files Affected**:
- Error handlers

**Description**:
Error responses don't follow consistent structure across all endpoints.

**Recommended Fix**:
```python
# Standardize error format
{
    "error": {
        "code": "INVALID_INPUT",
        "message": "Email is required",
        "details": {},
        "request_id": "uuid"
    }
}
```

---

### 18. Missing Health Check Dependencies

**Severity**: LOW
**Category**: Operations
**Files Affected**:
- `/home/llmtutor/llm_tutor/backend/src/app.py` (lines 151-197)

**Description**:
Health check endpoint tests database and Redis but not LLM service.

**Recommended Fix**:
```python
# Add LLM health check
try:
    llm_service = get_llm_service()
    llm_health = await llm_service.health_check()
    health_status["llm"] = "connected" if llm_health else "error"
except Exception:
    health_status["llm"] = "error"
    health_status["status"] = "degraded"  # Not unhealthy, just degraded
```

---

## Patterns to Watch (Not Yet Anti-Patterns)

### 19. Growing Service Classes

**Category**: Architecture
**Watch**:
- `AuthService` has many static methods
- Consider splitting into smaller, focused services
- Not urgent, but monitor for SRP violations

---

### 20. Frontend State Management Complexity

**Category**: Frontend Architecture
**Watch**:
- Redux slices growing
- May need state normalization strategy
- Consider Redux Toolkit Query for caching

---

## Summary Statistics

| Severity | Count |
|----------|-------|
| CRITICAL | 1     |
| HIGH     | 2     |
| MEDIUM   | 10    |
| LOW      | 7     |
| **Total**| **20**|

## Recommended Action Priority

### Immediate (This Sprint):
1. Fix #8: Remove Quart configuration monkey patch
2. Fix #1: Consolidate database session management
3. Fix #9: Add database pool monitoring

### Short Term (Next 2 Sprints):
4. Fix #7: Address email enumeration timing
5. Fix #13: Add request ID correlation
6. Fix #3: Improve configuration management

### Medium Term (Next Quarter):
7. Fix #15: Add migration testing
8. Refactor #19: Split large service classes
9. Standardize #17: Error response formats

---

## Document Control

**File Name:** anti-patterns.md
**Location:** /home/llmtutor/llm_tutor/plans/anti-patterns.md
**Version:** 1.0
**Date:** 2025-12-06
**Next Review:** 2026-01-06
**Classification:** Internal

**Changelog:**
- 2025-12-06 v1.0: Initial anti-patterns identification from architectural review
