import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { Provider } from 'react-redux';
import { BrowserRouter } from 'react-router-dom';
import { configureStore } from '@reduxjs/toolkit';
import ExerciseDashboardPage from './ExerciseDashboardPage';
import exerciseReducer from '../store/slices/exerciseSlice';
import authReducer from '../store/slices/authSlice';
import * as exerciseSlice from '../store/slices/exerciseSlice';

//Mock router navigation
const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

describe('ExerciseDashboardPage', () => {
  beforeEach(() => {
    // Mock the Redux thunks to prevent them from executing
    vi.spyOn(exerciseSlice, 'fetchDailyExercise').mockReturnValue({ type: 'noop' } as any);
    vi.spyOn(exerciseSlice, 'fetchExerciseHistory').mockReturnValue({ type: 'noop' } as any);
  });

  const renderPage = (exerciseState: any) => {
    const store = configureStore({
      reducer: {
        exercise: exerciseReducer,
        auth: authReducer,
      },
      preloadedState: {
        auth: {
          user: { id: 1, email: 'test@example.com', username: 'testuser' },
          token: 'test-token',
          isAuthenticated: true,
          loading: false,
          error: null,
        },
        exercise: exerciseState,
      },
    });

    return render(
      <Provider store={store}>
        <BrowserRouter>
          <ExerciseDashboardPage />
        </BrowserRouter>
      </Provider>
    );
  };

  it('should render page with testid', () => {
    renderPage({
      dailyExercise: null,
      currentExercise: null,
      exerciseHistory: [],
      loading: false,
      submitting: false,
      error: null,
      draftSolution: null,
      hints: [],
      hintsUsed: 0,
      submissionResult: null,
    });

    expect(screen.getByTestId('exercise-dashboard-page')).toBeInTheDocument();
  });

  it('should show loading state', () => {
    renderPage({
      dailyExercise: null,
      currentExercise: null,
      exerciseHistory: [],
      loading: true,
      submitting: false,
      error: null,
      draftSolution: null,
      hints: [],
      hintsUsed: 0,
      submissionResult: null,
    });

    expect(screen.getByText(/loading your daily exercise/i)).toBeInTheDocument();
  });

  it('should show empty state when no daily exercise', () => {
    renderPage({
      dailyExercise: null,
      currentExercise: null,
      exerciseHistory: [],
      loading: false,
      submitting: false,
      error: null,
      draftSolution: null,
      hints: [],
      hintsUsed: 0,
      submissionResult: null,
    });

    expect(screen.getByText(/no daily exercise available/i)).toBeInTheDocument();
  });

  it('should display daily exercise when available', () => {
    renderPage({
      dailyExercise: {
        exercise: {
          id: 1,
          title: 'Two Sum Problem',
          description: 'Find two numbers',
          difficulty: 'MEDIUM',
          language: 'python',
          exercise_type: 'algorithms',
          estimated_time_minutes: 30,
          learning_objectives: ['Arrays'],
          starter_code: '',
          test_cases: [],
          success_criteria: '',
          created_at: '2024-01-01T00:00:00Z',
        },
        status: 'in_progress',
        started_at: null,
        completed_at: null,
        is_daily: true,
      },
      currentExercise: null,
      exerciseHistory: [],
      loading: false,
      submitting: false,
      error: null,
      draftSolution: null,
      hints: [],
      hintsUsed: 0,
      submissionResult: null,
    });

    expect(screen.getByText('Two Sum Problem')).toBeInTheDocument();
    expect(screen.getByText('MEDIUM')).toBeInTheDocument();
  });

  it('should display exercise history', () => {
    renderPage({
      dailyExercise: null,
      currentExercise: null,
      exerciseHistory: [
        {
          id: 1,
          title: 'Past Exercise',
          difficulty: 'EASY',
          language: 'javascript',
          exercise_type: 'algorithms',
          completed_at: '2024-01-01T00:00:00Z',
          grade: 95,
          status: 'completed',
        },
      ],
      loading: false,
      submitting: false,
      error: null,
      draftSolution: null,
      hints: [],
      hintsUsed: 0,
      submissionResult: null,
    });

    expect(screen.getByText('Past Exercise')).toBeInTheDocument();
    expect(screen.getByText('95')).toBeInTheDocument();
  });

  it('should display error message', () => {
    renderPage({
      dailyExercise: null,
      currentExercise: null,
      exerciseHistory: [],
      loading: false,
      submitting: false,
      error: 'Failed to fetch',
      draftSolution: null,
      hints: [],
      hintsUsed: 0,
      submissionResult: null,
    });

    expect(screen.getByText(/failed to fetch/i)).toBeInTheDocument();
  });
});
