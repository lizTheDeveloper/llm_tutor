# Change: Add Exercise Generation & Management (D1)

## Why

The platform needs to generate personalized daily coding exercises based on user skill level, preferences, and learning goals. This is core to the "daily exercises" feature that drives user engagement and learning progression.

## What Changes

- LLM-powered exercise generation using GROQ API
- Exercise template system for different difficulty levels
- Exercise storage and retrieval API
- Exercise categorization (by language, topic, difficulty)
- User exercise assignment logic
- Exercise metadata tracking (completion rate, average time, difficulty rating)

## Impact

- **Affected specs**: exercise-management (new capability)
- **Affected code**:
  - `backend/src/api/exercises.py` (new endpoints)
  - `backend/src/services/exercise_service.py` (new service)
  - `backend/src/models/exercise.py` (extend existing model)
  - `backend/src/services/llm/prompt_templates.py` (add exercise generation templates)
- **Dependencies**: B2 (LLM Integration), B3 (Database Schema), C2 (User Memory)
- **Unblocks**: D2 (Progress Tracking), D4 (Exercise UI)
