# Anti-Pattern Checklist
## LLM Coding Tutor Platform

**Last Updated:** 2025-12-05
**Version:** 1.0

This checklist documents known anti-patterns, code smells, and architectural issues to watch for during code reviews. Each anti-pattern includes detection criteria, severity, and remediation guidance.

---

## 1. Security Anti-Patterns

### AP-SEC-001: Hardcoded Secrets in Code
**Category:** Security
**Severity:** CRITICAL
**Description:** Hardcoded API keys, passwords, tokens, or other secrets directly in source code instead of environment variables.

**Problem:**
- Secrets get committed to version control
- Difficult to rotate credentials
- Increases attack surface
- Violates security best practices

**Detection:**
- Search for patterns: `password =`, `api_key =`, `secret =`, `token =` followed by string literals
- Look for suspicious base64 or hex strings
- Check for `SECRET_KEY = "..."` in Python files

**Fix:**
- Use environment variables via `.env` files
- Use secrets management systems (AWS Secrets Manager, HashiCorp Vault)
- Never commit `.env` files (ensure in `.gitignore`)

**Example:**
```python
# BAD
API_KEY = "sk-1234567890abcdef"

# GOOD
import os
API_KEY = os.getenv("API_KEY")
```

---

### AP-SEC-002: Weak Password Validation
**Category:** Security
**Severity:** HIGH
**Description:** Insufficient password requirements allowing weak passwords that are easily compromised.

**Problem:**
- Users can set easily guessable passwords
- Vulnerable to brute force attacks
- Fails compliance requirements (NIST, PCI-DSS)

**Detection:**
- Check password validation regex/logic
- Look for minimum length < 12 characters
- Missing complexity requirements

**Fix:**
- Minimum 12 characters
- Require mixed case, numbers, special characters
- Use strong password hashing (bcrypt with cost factor >= 12)

---

### AP-SEC-003: Missing Input Validation
**Category:** Security
**Severity:** HIGH
**Description:** User input accepted without proper validation, sanitization, or escaping.

**Problem:**
- SQL injection vulnerabilities
- XSS attacks
- Command injection
- Data corruption

**Detection:**
- Direct string concatenation in SQL queries
- User input used in shell commands
- HTML rendering without escaping
- Missing Pydantic validation on API endpoints

**Fix:**
- Use parameterized queries/ORM
- Validate with Pydantic schemas
- Sanitize and escape all user input
- Use allowlists over blocklists

---

### AP-SEC-004: Insufficient Session Management
**Category:** Security
**Severity:** HIGH
**Description:** JWT tokens stored insecurely or sessions not properly invalidated.

**Problem:**
- Token theft via XSS
- Session fixation attacks
- Inability to revoke compromised tokens

**Detection:**
- JWT tokens stored in localStorage (vulnerable to XSS)
- No session tracking in Redis/database
- Missing logout functionality
- No token expiration

**Fix:**
- Store JWT in httpOnly, secure, sameSite cookies
- Track sessions in Redis with expiration
- Implement proper logout with token invalidation
- Use refresh token rotation

---

## 2. Performance Anti-Patterns

### AP-PERF-001: N+1 Query Problem
**Category:** Performance
**Severity:** CRITICAL
**Description:** Executing N additional database queries inside a loop instead of a single optimized query.

**Problem:**
- Severe performance degradation with scale
- Database connection pool exhaustion
- High latency for users

**Detection:**
- Database queries inside loops
- Lack of eager loading (select_related, joinedload)
- Multiple round trips for related data

**Fix:**
- Use eager loading (SQLAlchemy `selectinload`, `joinedload`)
- Batch queries with `IN` clauses
- Use `SELECT_RELATED` in ORM
- Implement DataLoader pattern for GraphQL

**Example:**
```python
# BAD - N+1 queries
for user in users:
    profile = await session.execute(
        select(Profile).where(Profile.user_id == user.id)
    )

# GOOD - Single query with join
users = await session.execute(
    select(User).options(selectinload(User.profile))
)
```

---

### AP-PERF-002: Missing Database Indexes
**Category:** Performance
**Severity:** HIGH
**Description:** Queries on unindexed columns causing full table scans.

**Problem:**
- Slow query performance
- Database CPU/IO spikes
- Poor scalability

**Detection:**
- Queries on columns without indexes
- WHERE clauses on non-indexed fields
- Foreign keys without indexes
- Slow query logs

**Fix:**
- Add indexes to frequently queried columns
- Index foreign keys
- Use composite indexes for multi-column queries
- Monitor and optimize with EXPLAIN

---

### AP-PERF-003: Unbounded Data Fetches
**Category:** Performance
**Severity:** MEDIUM
**Description:** Fetching all records without pagination or limits.

**Problem:**
- Memory exhaustion
- Slow API responses
- Poor user experience
- Database overload

**Detection:**
- `SELECT * FROM` without LIMIT
- Missing pagination parameters
- Loading entire collections in memory

**Fix:**
- Implement cursor or offset pagination
- Default page size limits (e.g., 50)
- Use streaming for large datasets
- Implement lazy loading

---

### AP-PERF-004: Synchronous I/O in Async Context
**Category:** Performance
**Severity:** MEDIUM
**Description:** Using blocking synchronous operations in async/await code paths.

**Problem:**
- Blocks event loop
- Reduces concurrency
- Degrades overall application performance

**Detection:**
- Non-async database calls in async functions
- `requests` library instead of `httpx`/`aiohttp`
- File I/O without async variants
- Synchronous Redis calls in async code

**Fix:**
- Use async libraries (aiohttp, asyncpg, aiomysql)
- Use asyncio-compatible Redis client
- Run blocking operations in executor pool

---

## 3. Code Quality Anti-Patterns

### AP-CODE-001: God Class/Object
**Category:** Code Quality
**Severity:** MEDIUM
**Description:** Single class or module doing too many unrelated things, violating Single Responsibility Principle.

**Problem:**
- Hard to understand and maintain
- Difficult to test
- Tight coupling
- Code reuse issues

**Detection:**
- Classes > 500 lines
- Many unrelated methods
- High cyclomatic complexity
- Imports from many different domains

**Fix:**
- Split into smaller, focused classes
- Extract services or utilities
- Apply Single Responsibility Principle
- Use composition over inheritance

---

### AP-CODE-002: Primitive Obsession
**Category:** Code Quality
**Severity:** LOW
**Description:** Using primitive types (strings, dicts) instead of domain objects or value objects.

**Problem:**
- Type safety issues
- Validation scattered everywhere
- Hard to refactor
- Easy to misuse

**Detection:**
- Functions with many string/int parameters
- Dicts used for structured data
- Type hints showing primitive types

**Fix:**
- Use Pydantic models
- Create value objects
- Use enums for constrained values
- Type-safe domain models

---

### AP-CODE-003: Magic Numbers/Strings
**Category:** Code Quality
**Severity:** LOW
**Description:** Hardcoded literal values without named constants.

**Problem:**
- Unclear intent
- Hard to maintain
- Duplication
- Error-prone changes

**Detection:**
- Unexplained numeric literals
- Repeated string values
- No constants defined

**Fix:**
- Extract to named constants
- Use enums for related values
- Document meaning

**Example:**
```python
# BAD
if user.age >= 18:
    # ...

# GOOD
MINIMUM_AGE = 18
if user.age >= MINIMUM_AGE:
    # ...
```

---

### AP-CODE-004: Inconsistent Error Handling
**Category:** Code Quality
**Severity:** MEDIUM
**Description:** Different error handling patterns across the codebase.

**Problem:**
- Unpredictable behavior
- Difficult debugging
- Poor user experience
- Missing error context

**Detection:**
- Mix of exceptions and error codes
- Silent failures (empty except blocks)
- Errors not logged
- Inconsistent error responses

**Fix:**
- Standardize on exception-based error handling
- Use custom exception hierarchy
- Always log errors with context
- Return consistent error response format

---

## 4. Architecture Anti-Patterns

### AP-ARCH-001: Tight Coupling Between Layers
**Category:** Architecture
**Severity:** HIGH
**Description:** Direct dependencies between presentation, business, and data layers.

**Problem:**
- Hard to test
- Difficult to change
- Cannot swap implementations
- Violates dependency inversion

**Detection:**
- API routes calling database directly
- Business logic in route handlers
- Database models in API responses

**Fix:**
- Introduce service layer
- Use dependency injection
- Define clear interfaces
- Apply clean architecture principles

---

### AP-ARCH-002: Missing Abstraction Layer
**Category:** Architecture
**Severity:** MEDIUM
**Description:** Direct dependency on external services without abstraction.

**Problem:**
- Vendor lock-in
- Hard to test (cannot mock easily)
- Difficult to switch providers
- Scattered integration logic

**Detection:**
- Direct API client usage in business logic
- No interface/protocol definitions
- Provider-specific code throughout

**Fix:**
- Define provider interfaces
- Use adapter pattern
- Implement factory pattern
- Centralize provider logic

---

### AP-ARCH-003: Shared Mutable State
**Category:** Architecture
**Severity:** HIGH
**Description:** Global or shared state modified by multiple components without synchronization.

**Problem:**
- Race conditions
- Non-deterministic bugs
- Thread safety issues
- Hard to debug

**Detection:**
- Global variables modified by functions
- Class-level mutable state
- No locking mechanisms

**Fix:**
- Use immutable data structures
- Implement proper locking
- Use message passing
- Functional programming patterns

---

### AP-ARCH-004: Missing Feature Flags
**Category:** Architecture
**Severity:** LOW
**Description:** No mechanism to toggle features on/off at runtime.

**Problem:**
- Cannot do gradual rollouts
- Risky deployments
- Hard to A/B test
- Difficult rollback

**Detection:**
- No feature flag system
- Features enabled/disabled with code changes
- No configuration management

**Fix:**
- Implement feature flag system
- Use environment-based config
- Support runtime toggles
- Implement A/B testing framework

---

## 5. Testing Anti-Patterns

### AP-TEST-001: Excessive Mocking
**Category:** Testing
**Severity:** MEDIUM
**Description:** Over-mocking internal components instead of testing real integrations.

**Problem:**
- Tests don't catch real bugs
- Brittle tests
- False confidence
- Tests tied to implementation details

**Detection:**
- Mocking internal services
- More mock setup than test logic
- Mocking everything except function under test

**Fix:**
- Test real integrations
- Mock only external dependencies (APIs, databases)
- Use test databases for integration tests
- Focus on behavior, not implementation

---

### AP-TEST-002: Missing Test Data Factories
**Category:** Testing
**Severity:** LOW
**Description:** Test data created manually in each test, leading to duplication and brittleness.

**Problem:**
- Duplicated test data creation
- Hard to maintain tests
- Obscures test intent
- Easy to create invalid test data

**Detection:**
- Repeated data creation code
- Long test setup sections
- Hardcoded test values

**Fix:**
- Implement factory pattern (Factory Boy)
- Create test data builders
- Use fixtures effectively
- Parameterize tests

---

### AP-TEST-003: Test Interdependence
**Category:** Testing
**Severity:** HIGH
**Description:** Tests that depend on other tests running first or shared state.

**Problem:**
- Non-deterministic failures
- Hard to debug
- Cannot run tests in parallel
- Cannot run single tests

**Detection:**
- Tests fail when run in isolation
- Tests have required run order
- Shared global state
- Test database not reset

**Fix:**
- Make tests independent
- Reset state before each test
- Use test fixtures properly
- Implement proper teardown

---

## 6. Documentation Anti-Patterns

### AP-DOC-001: Missing API Documentation
**Category:** Documentation
**Severity:** MEDIUM
**Description:** API endpoints without OpenAPI/Swagger documentation.

**Problem:**
- Hard for frontend developers
- No contract testing
- API versioning issues
- Manual API testing

**Detection:**
- No OpenAPI spec
- Missing docstrings
- No request/response examples

**Fix:**
- Generate OpenAPI from code
- Document all endpoints
- Include examples
- Version API properly

---

### AP-DOC-002: Outdated Documentation
**Category:** Documentation
**Severity:** LOW
**Description:** Documentation not kept in sync with code changes.

**Problem:**
- Misleading information
- Wastes developer time
- Reduces trust
- Training issues

**Detection:**
- Documentation mentions removed features
- Examples don't work
- Screenshots outdated
- No documentation update process

**Fix:**
- Documentation in code (docstrings)
- Generate docs from code
- Documentation review in PR process
- Regular documentation audits

---

## Usage Instructions

During code reviews, systematically check for these anti-patterns:

1. **Pre-commit**: Run automated checks (linters, security scanners)
2. **PR Review**: Reference this checklist for manual review
3. **Add new patterns**: Document recurring issues you find
4. **Update severity**: Adjust based on actual impact
5. **Track metrics**: Count occurrences to prioritize fixes

## Severity Levels

- **CRITICAL**: Security vulnerabilities, data loss risk, system-wide failure
- **HIGH**: Major performance issues, architectural flaws, scalability blockers
- **MEDIUM**: Code quality issues, maintainability concerns, technical debt
- **LOW**: Minor issues, style inconsistencies, nice-to-have improvements

---

**Document Owner:** Autonomous Reviewer Agent
**Review Frequency:** Monthly or after major changes
**Next Review:** 2026-01-05
