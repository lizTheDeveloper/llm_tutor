# Project Context

## Purpose

**LLM Coding Tutor Platform** (working name: "CodeMentor") - An adaptive web-based learning system that leverages large language models to provide personalized coding education through daily exercises, adaptive difficulty, community learning, and mentorship.

### Key Features
- Personalized onboarding interview to assess skill level and goals
- Daily coding exercises with adaptive difficulty
- AI-powered Socratic tutoring using GROQ LLM
- User memory and context tracking with vector embeddings
- OAuth authentication (GitHub, Google)
- Progress tracking and achievements

## Tech Stack

### Backend
- **Language**: Python 3.11+
- **Framework**: Quart (async Flask alternative)
- **Database**: PostgreSQL with asyncpg driver
- **Cache/Sessions**: Redis with async support
- **ORM**: SQLAlchemy (async) with Alembic migrations
- **Authentication**: JWT tokens, bcrypt password hashing
- **LLM Provider**: GROQ API (llama-3.3-70b-versatile model)
- **Testing**: pytest with async support

### Frontend
- **Language**: TypeScript
- **Framework**: React 19
- **Build Tool**: Vite
- **State Management**: Redux Toolkit
- **UI Library**: Material-UI (MUI)
- **HTTP Client**: Axios
- **Testing**: Vitest + React Testing Library
- **Routing**: React Router

### Infrastructure
- **Containerization**: Docker
- **Cloud Platform**: Google Cloud Platform (GCP)
- **CI/CD**: GitHub Actions (planned)
- **Monitoring**: Structured logging with Python logging module

## Project Conventions

### Code Style

**General**:
- Never use single-letter variable names
- Always use descriptive, meaningful names
- Prefer explicit over implicit
- No emoji in code unless explicitly requested

**Python**:
- Prefer raw SQL over SQLAlchemy except for model definition
- Always use virtual environment (venv, NOT conda)
- Use type hints where beneficial
- Follow PEP 8 style guide
- Use async/await for I/O operations

**TypeScript/React**:
- Use functional components with hooks
- TypeScript strict mode enabled
- Prefer composition over inheritance
- Use Redux Toolkit for state management

**Environment**:
- Always activate virtual environment before running Python code
- Virtual environment typically in `./venv` or `./env`
- Check available RAM before running memory-intensive experiments (64GB available)

### Architecture Patterns

**Backend**:
- **Service Layer Pattern**: Business logic in service modules (e.g., `auth_service.py`, `llm_service.py`, `profile_service.py`)
- **Middleware**: Cross-cutting concerns (authentication, rate limiting, security headers)
- **Repository Pattern**: Database operations abstracted in service layer
- **Provider Pattern**: LLM provider abstraction for future provider switching
- **Async Throughout**: All I/O operations use async/await

**Frontend**:
- **Redux Slices**: Feature-based state management with async thunks
- **Protected Routes**: Authentication-based route guards
- **Service Layer**: API calls abstracted in service modules
- **Component Organization**: Pages, components, hooks, services separation

**Database**:
- **Migrations**: Alembic for schema versioning
- **Indexes**: Performance indexes on frequently-queried columns
- **Foreign Keys**: Enforce referential integrity with CASCADE
- **Connection Pool**: Async connection pooling for scalability

### Testing Strategy

**Philosophy**:
- Prioritize integration testing over heavily mocked unit tests
- Test real interactions between components
- Only mock external dependencies (APIs, databases) when absolutely necessary
- Test actual integration points where bugs commonly occur
- Write tests that exercise the same code paths users will use

**Backend**:
- Integration tests with real database (test database)
- Mock external APIs (GROQ, OAuth providers)
- Test authentication flows end-to-end
- Coverage focus on critical paths (auth, data integrity)

**Frontend**:
- Component integration tests with Redux
- Mock API calls at the boundary
- Test user interactions and state changes
- Responsive design testing

**Important**:
- Never comment out existing features to "simplify for now"
- Create separate test files or scripts for isolated testing
- Use feature flags if temporary disabling is needed

### Git Workflow

**Branching**:
- Main branch: `main` (primary development branch)
- Direct commits to main for solo development
- Feature branches for experimental work (optional)

**Commit Conventions**:
- Descriptive commit messages explaining the "why"
- Include emoji footer: 🤖 Generated with [Claude Code](https://claude.com/claude-code)
- Co-author attribution: `Co-Authored-By: Claude <noreply@anthropic.com>`
- Use heredoc for multi-line commit messages

**Example**:
```bash
git commit -m "$(cat <<'EOF'
Add user authentication system with OAuth

- Implemented JWT token generation and validation
- Added GitHub and Google OAuth integration
- RBAC middleware with role-based access control

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>
EOF
)"
```

**Documentation**:
- Save all plans in `/plans` directory
- Save markdown diary entries in `/devlog` under feature name
- Always check in plans and devlog entries
- Maintain roadmap.md with work stream tracking

## Domain Context

### Educational Platform Concepts

**Socratic Teaching Method**:
- Guide learners through questions rather than direct answers
- Help students discover solutions themselves
- Adapt difficulty based on responses
- Encourage critical thinking and problem-solving

**Adaptive Difficulty**:
- Track user skill level and progress
- Adjust exercise complexity dynamically
- Personalize based on learning speed and preferences

**User Memory System**:
- Vector embeddings of user interactions and progress
- Context injection into LLM prompts
- Personalization scoring algorithm
- Exercise history tracking

**Onboarding Interview**:
- Multi-step form to assess:
  - Programming language preferences
  - Current skill level
  - Career goals
  - Learning style preferences
  - Time commitment
- Resume capability for incomplete interviews
- Profile editing post-onboarding

## Important Constraints

### Technical Constraints
- **Platform**: macOS (Macbook Pro M3, 64GB RAM)
- **Python Environment**: MUST use venv, NEVER use Conda
- **Node.js Version**: 20.19.0+ (currently 22.12.0)
- **Database**: PostgreSQL with async driver (asyncpg)
- **Redis**: Required for sessions and rate limiting

### Development Constraints
- Always activate virtual environment before Python operations
- Check documentation before using libraries (expert approach)
- Don't hallucinate - verify before implementing
- Execute rather than teach - implement solutions directly
- Background long-running processes (web servers)

### Security Constraints
- OAuth tokens must NEVER be in URLs (use code exchange flow)
- All passwords hashed with bcrypt
- Rate limiting on authentication endpoints
- Security headers on all responses
- JWT secret keys must be strong and unique
- Session invalidation on password reset

## External Dependencies

### APIs and Services

**GROQ API**:
- Model: llama-3.3-70b-versatile
- Rate Limits: 30 RPM, 14,400 RPD
- Pricing: $0.59 input / $0.79 output per 1M tokens
- Fallback: Compound model (groq/compound)

**OAuth Providers**:
- GitHub OAuth (account linking supported)
- Google OAuth (account linking supported)
- Callback URL configuration required

**Database**:
- PostgreSQL (local or GCP Cloud SQL)
- Connection pooling with asyncpg
- Database: codementor (production), codementor_test (testing)

**Cache/Session Store**:
- Redis (localhost:6379)
- Database 0: Production cache
- Database 15: Test cache
- TTL: 1 hour for LLM response cache

### Infrastructure Services

**GCP Services** (planned):
- Compute Engine for VM hosting
- Cloud SQL for PostgreSQL
- Cloud Storage for static assets
- Cloud Run (potential serverless option)

### Development Tools
- **Alembic**: Database migrations
- **pytest**: Backend testing
- **Vitest**: Frontend testing
- **Playwright**: End-to-end testing (for web verification)
- **OpenSpec**: Specification-driven development
- **Claude Code**: AI development assistant

## Project Status

**Current Phase**: Phase 0 - MVP Foundation
**Current Stage**: Stage 3 - User Onboarding & LLM Tutor
**Progress**: 4/5 work streams complete (C1, C2, C3, C4 complete; C5 pending)

**Completed**:
- ✅ Infrastructure and framework setup
- ✅ Authentication system with OAuth
- ✅ Database schema and migrations
- ✅ LLM integration with GROQ
- ✅ User memory and personalization engine
- ✅ Onboarding interview (backend + frontend)
- ✅ LLM tutor chat API

**In Progress**:
- ⚪ C5: Chat Interface UI (frontend)

**Next Stage**: Stage 4 - Daily Exercise System & Progress Tracking

For detailed roadmap, see `/plans/roadmap.md`.
