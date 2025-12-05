# LLM Coding Tutor Platform - Active Roadmap

## Document Version: 1.9
## Date: 2025-12-05
## Status: Stage 3 - ACTIVE

---

## Current Phase: Phase 0 - MVP Foundation

### Stage 3: User Onboarding & LLM Tutor

**Goal**: Build onboarding interview and chat interface. High parallelization potential.

**Status**: ACTIVE - All dependencies complete, ready to execute

**Prerequisites**: All Stage 2 work complete (see archive for details)

---

#### Work Stream C1: Onboarding Interview Backend
**Agent**: Backend Engineer #1
**Dependencies**: None (B1, B3 complete)
**Status**: ⚪ Not Started
**Parallel With**: C2, C3, C4, C5

**Tasks:**
- [ ] User profile creation endpoint
- [ ] Onboarding interview questions API
- [ ] Save interview responses endpoint
- [ ] Resume interview logic
- [ ] Profile update endpoint
- [ ] Profile retrieval endpoint
- [ ] Validation for interview data

**Deliverable**: User profile and onboarding API

**Effort**: M

**Done When**:
- API endpoints functional and tested
- User can complete interview and save profile
- User can resume partially completed interview
- Profile data properly validated and stored

---

#### Work Stream C2: User Memory & Personalization
**Agent**: Backend Engineer #2
**Dependencies**: None (B2, B3 complete)
**Status**: ⚪ Not Started
**Parallel With**: C1, C3, C4, C5

**Tasks:**
- [ ] Vector database setup (Pinecone or PostgreSQL + pgvector)
- [ ] User memory storage service
- [ ] Profile embedding generation
- [ ] Exercise history tracking
- [ ] Interaction logging
- [ ] Memory retrieval for LLM context
- [ ] Memory update triggers (on exercise completion, chat, etc.)
- [ ] Personalization scoring algorithm

**Deliverable**: User memory and personalization engine

**Effort**: M

**Done When**:
- Vector database operational
- User interactions stored and retrievable
- Profile embeddings generated
- Memory retrieval integrated with LLM context
- Personalization scores calculated

---

#### Work Stream C3: LLM Tutor Backend
**Agent**: Backend Engineer #3
**Dependencies**: None (B2 complete; C2 soft dependency)
**Status**: ⚪ Not Started
**Parallel With**: C1, C2, C4, C5
**Note**: Can build API structure immediately; memory integration happens later

**Tasks:**
- [ ] Chat message endpoint (send/receive)
- [ ] Conversation history storage
- [ ] LLM tutor system prompt engineering
- [ ] Context injection (user memory, preferences, goals)
- [ ] Socratic method prompt refinement
- [ ] Skill level adaptation in prompts
- [ ] Code formatting in responses
- [ ] Conversation history retrieval endpoint
- [ ] Real-time response streaming (optional)

**Deliverable**: LLM tutor chat API with personalization

**Effort**: M

**Done When**:
- Chat API endpoints functional
- LLM responses personalized to user context
- Socratic teaching method demonstrated
- Code blocks properly formatted
- Conversation history persisted and retrievable
- Integration tests passing

---

#### Work Stream C4: Onboarding Interview UI
**Agent**: Frontend Engineer #1
**Dependencies**: None (A3, A4 complete)
**Status**: ⚪ Not Started
**Parallel With**: C1, C2, C3, C5

**Tasks:**
- [ ] Multi-step interview form component
- [ ] Question screens for:
  - Programming language selection
  - Skill level assessment
  - Career goals input
  - Learning style preferences
  - Time commitment
- [ ] Progress indicator
- [ ] Save and resume functionality
- [ ] Form validation
- [ ] Profile edit page
- [ ] Profile display component

**Deliverable**: Complete onboarding UI flow

**Effort**: M

**Done When**:
- Multi-step interview UI complete
- All question types implemented
- Progress indicator functional
- Save/resume working
- Form validation complete
- Profile edit and display pages ready
- Responsive on mobile/tablet/desktop

---

#### Work Stream C5: Chat Interface UI
**Agent**: Frontend Engineer #2
**Dependencies**: None (A3, A4 complete)
**Status**: ⚪ Not Started
**Parallel With**: C1, C2, C3, C4

**Tasks:**
- [ ] Chat interface layout (sidebar or full-screen)
- [ ] Message list component with scrolling
- [ ] Message input component
- [ ] Message bubbles (user vs. tutor)
- [ ] Typing indicator
- [ ] Loading states during LLM processing
- [ ] Syntax highlighting for code snippets (Prism.js)
- [ ] Markdown rendering in messages
- [ ] Copy-to-clipboard for code
- [ ] Chat history navigation
- [ ] Responsive design for mobile

**Deliverable**: Complete chat UI

**Effort**: M

**Done When**:
- Chat interface responsive and functional
- Messages display correctly (user/tutor differentiation)
- Code syntax highlighting working
- Markdown rendering operational
- Copy-to-clipboard functional
- Loading states visible during LLM responses
- Mobile responsive

---

## INTEGRATION CHECKPOINT - Stage 3 Complete

**Completion Criteria:**
- [ ] Onboarding flow works end-to-end (C1 + C4)
- [ ] Chat interface functional with LLM responses (C3 + C5)
- [ ] User memory system storing and retrieving data (C2)
- [ ] All UIs integrated with backends
- [ ] End-to-end testing complete
- [ ] New user can register, onboard, and chat with tutor

**Next Stage**: Stage 4 - Daily Exercise System & Progress Tracking

---

## Backlog

### Future Stages (Not Yet Started)
- **Phase 0, Stage 4**: Daily Exercises & Progress Tracking
  - D1: Exercise Generation & Management (backend)
  - D2: Progress Tracking Backend
  - D3: Difficulty Adaptation Engine
  - D4: Exercise UI Components

- **Phase 1.5**: Enhanced MVP Features
  - GitHub Integration
  - Achievement System
  - User Dashboard

- **Phase 2**: Community & Social Features
  - Matrix chat integration
  - Community rooms
  - Peer code review

- **Phase 3**: Mentorship & Advanced Features
  - Mentor-mentee matching
  - Group projects
  - Advanced analytics

- **Phase 4**: Analytics & Business Features
  - Admin dashboard
  - Usage analytics
  - Business metrics

For detailed planning of future phases, see requirements.md and priorities.md.

---

## Archive Reference

**Stage 1 (Infrastructure & Foundation)**: COMPLETE - Archived 2025-12-05
- A1: Infrastructure Setup
- A2: Backend Framework Setup
- A3: Frontend Framework Setup
- A4: Design System & Wireframes

**Stage 2 (Authentication & Data Models)**: COMPLETE - Archived 2025-12-05
- B1: Authentication System
- B2: LLM Integration Layer
- B3: Database Schema & Models
- B4: Authentication UI

All completed work archived in `/Users/annhoward/src/llm_tutor/plans/completed/roadmap-archive.md`

---

## Document Control

**File Name:** roadmap.md
**Location:** /Users/annhoward/src/llm_tutor/plans/roadmap.md
**Version:** 1.9
**Date:** 2025-12-05
**Status:** Active - Stage 3 In Progress
**Classification:** Internal

**Related Documents:**
- requirements.md (v1.2) - Source requirements
- priorities.md (v1.0) - Feature prioritization
- completed/roadmap-archive.md - Stages 1 & 2 complete

---

**END OF DOCUMENT**
