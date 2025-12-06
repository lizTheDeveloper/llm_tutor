import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { Provider } from 'react-redux';
import { BrowserRouter } from 'react-router-dom';
import { configureStore } from '@reduxjs/toolkit';
import ProgressDashboardPage from './ProgressDashboardPage';
import progressReducer from '../store/slices/progressSlice';
import authReducer from '../store/slices/authSlice';
import * as progressSlice from '../store/slices/progressSlice';

const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

describe('ProgressDashboardPage', () => {
  beforeEach(() => {
    // Mock the Redux thunks to prevent them from executing
    vi.spyOn(progressSlice, 'fetchProgressMetrics').mockReturnValue({ type: 'noop' } as any);
    vi.spyOn(progressSlice, 'fetchAchievements').mockReturnValue({ type: 'noop' } as any);
    vi.spyOn(progressSlice, 'fetchBadges').mockReturnValue({ type: 'noop' } as any);
  });

  const renderPage = (progressState: any) => {
    const store = configureStore({
      reducer: {
        progress: progressReducer,
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
        progress: progressState,
      },
    });

    return render(
      <Provider store={store}>
        <BrowserRouter>
          <ProgressDashboardPage />
        </BrowserRouter>
      </Provider>
    );
  };

  it('should render page with testid', () => {
    renderPage({
      metrics: null,
      achievements: [],
      history: [],
      statistics: null,
      badges: [],
      skillLevels: [],
      loading: false,
      error: null,
    });

    expect(screen.getByTestId('progress-dashboard-page')).toBeInTheDocument();
  });

  it('should show loading state', () => {
    renderPage({
      metrics: null,
      achievements: [],
      history: [],
      statistics: null,
      badges: [],
      skillLevels: [],
      loading: true,
      error: null,
    });

    expect(screen.getByText(/loading/i)).toBeInTheDocument();
  });

  it('should display progress metrics', () => {
    renderPage({
      metrics: {
        exercises_completed: 25,
        current_streak: 7,
        longest_streak: 15,
        average_grade: 88.5,
        total_time_minutes: 1200,
        exercises_by_difficulty: { EASY: 10, MEDIUM: 10, HARD: 5 },
        exercises_by_type: { algorithms: 15, debugging: 5, practical: 5 },
        last_exercise_date: '2024-01-01T00:00:00Z',
        user_id: 1,
      },
      achievements: [],
      history: [],
      statistics: null,
      badges: [],
      skillLevels: [],
      loading: false,
      error: null,
    });

    expect(screen.getByText('25')).toBeInTheDocument(); // exercises completed
    expect(screen.getByText('7')).toBeInTheDocument(); // current streak
    expect(screen.getByText('88.5')).toBeInTheDocument(); // average grade
  });

  it('should display achievements', () => {
    renderPage({
      metrics: null,
      achievements: [
        {
          id: 1,
          title: 'First Steps',
          description: 'Complete your first exercise',
          icon: 'star',
          category: 'milestones',
          criteria_type: 'exercises_completed',
          criteria_value: 1,
          unlocked: true,
          unlocked_at: '2024-01-01T00:00:00Z',
          user_id: 1,
          current_value: 25,
          progress_percentage: 100,
        },
      ],
      history: [],
      statistics: null,
      badges: [],
      skillLevels: [],
      loading: false,
      error: null,
    });

    expect(screen.getByText('First Steps')).toBeInTheDocument();
  });

  it('should display error message', () => {
    renderPage({
      metrics: null,
      achievements: [],
      history: [],
      statistics: null,
      badges: [],
      skillLevels: [],
      loading: false,
      error: 'Failed to load progress',
    });

    expect(screen.getByText(/failed to load progress/i)).toBeInTheDocument();
  });
});
