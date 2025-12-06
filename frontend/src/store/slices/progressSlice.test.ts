/**
 * Test Suite for Progress Redux Slice
 *
 * Test Strategy:
 * - Test all Redux state management for progress tracking functionality
 * - Test async thunks for D2 API integration (metrics, achievements, streaks, badges)
 * - Test state updates for loading, error, and success cases
 * - Mock API calls to test integration without external dependencies
 * - Test progress workflow: fetch metrics -> view achievements -> export data
 * - Integration tests over unit tests - test real code paths users will execute
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';
import progressReducer, {
  fetchProgressMetrics,
  fetchAchievements,
  fetchProgressHistory,
  fetchStatistics,
  fetchBadges,
  fetchSkillLevels,
  exportProgressData,
  clearError,
  ProgressState,
} from './progressSlice';
import { configureStore } from '@reduxjs/toolkit';
import axios from 'axios';

// Mock axios
vi.mock('axios');
const mockedAxios = vi.mocked(axios, true);

describe('progressSlice', () => {
  let store: ReturnType<typeof configureStore>;

  beforeEach(() => {
    // Reset mocks
    vi.clearAllMocks();

    // Create fresh store for each test
    store = configureStore({
      reducer: {
        progress: progressReducer,
      },
    });

    // Mock axios create to return mocked axios instance
    mockedAxios.create = vi.fn(() => mockedAxios as any);
  });

  describe('initial state', () => {
    it('should have correct initial state', () => {
      const state = store.getState().progress;

      expect(state.metrics).toBeNull();
      expect(state.achievements).toEqual([]);
      expect(state.history).toEqual([]);
      expect(state.statistics).toBeNull();
      expect(state.badges).toEqual([]);
      expect(state.skillLevels).toEqual([]);
      expect(state.loading).toBe(false);
      expect(state.error).toBeNull();
    });
  });

  describe('synchronous actions', () => {
    it('should clear error', () => {
      const initialState: ProgressState = {
        metrics: null,
        achievements: [],
        history: [],
        statistics: null,
        badges: [],
        skillLevels: [],
        loading: false,
        error: 'Test error',
      };

      const state = progressReducer(initialState, clearError());

      expect(state.error).toBeNull();
    });
  });

  describe('fetchProgressMetrics', () => {
    it('should fetch progress metrics successfully', async () => {
      const mockResponse = {
        data: {
          exercises_completed: 42,
          current_streak: 7,
          longest_streak: 14,
          total_time_spent_seconds: 86400,
          average_grade: 87.5,
          achievements: [
            { id: 1, name: '7 Day Streak', unlocked: true, points: 50 },
          ],
          skill_levels: {
            python: { level: 'intermediate', exercises_completed: 20 },
          },
        },
      };

      mockedAxios.get = vi.fn().mockResolvedValue(mockResponse);

      await store.dispatch(fetchProgressMetrics());
      const state = store.getState().progress;

      expect(state.loading).toBe(false);
      expect(state.metrics).toEqual(mockResponse.data);
      expect(state.error).toBeNull();
      expect(mockedAxios.get).toHaveBeenCalled();
    });

    it('should handle fetch metrics error', async () => {
      const mockError = new Error('Failed to fetch metrics');
      mockedAxios.get = vi.fn().mockRejectedValue(mockError);

      await store.dispatch(fetchProgressMetrics());
      const state = store.getState().progress;

      expect(state.loading).toBe(false);
      expect(state.metrics).toBeNull();
      expect(state.error).toBe('Failed to fetch metrics');
    });

    it('should set loading state while fetching', async () => {
      const mockPromise = new Promise((resolve) => setTimeout(resolve, 100));
      mockedAxios.get = vi.fn().mockReturnValue(mockPromise);

      const dispatchPromise = store.dispatch(fetchProgressMetrics());
      const state = store.getState().progress;

      expect(state.loading).toBe(true);

      await dispatchPromise;
    });
  });

  describe('fetchAchievements', () => {
    it('should fetch achievements successfully', async () => {
      const mockResponse = {
        data: {
          achievements: [
            {
              id: 1,
              name: 'First Steps',
              slug: 'first_steps',
              title: 'Complete Your First Exercise',
              description: 'Complete your very first coding exercise',
              category: 'milestone',
              requirement_value: 1,
              requirement_description: 'Complete 1 exercise',
              points: 10,
              unlocked: true,
              unlocked_at: '2025-12-01T10:00:00Z',
              progress: 1,
              target: 1,
              progress_percentage: 100,
            },
            {
              id: 2,
              name: '7 Day Streak',
              slug: 'streak_7',
              title: '7 Day Streak',
              description: 'Maintain a 7 day coding streak',
              category: 'streak',
              requirement_value: 7,
              requirement_description: 'Maintain 7 day streak',
              points: 50,
              unlocked: true,
              unlocked_at: '2025-12-05T10:00:00Z',
              progress: 7,
              target: 7,
              progress_percentage: 100,
            },
            {
              id: 3,
              name: '30 Day Streak',
              slug: 'streak_30',
              title: '30 Day Streak',
              description: 'Maintain a 30 day coding streak',
              category: 'streak',
              requirement_value: 30,
              requirement_description: 'Maintain 30 day streak',
              points: 200,
              unlocked: false,
              progress: 7,
              target: 30,
              progress_percentage: 23.33,
            },
          ],
          total_points: 60,
          unlocked_count: 2,
          total_count: 3,
        },
      };

      mockedAxios.get = vi.fn().mockResolvedValue(mockResponse);

      await store.dispatch(fetchAchievements());
      const state = store.getState().progress;

      expect(state.loading).toBe(false);
      expect(state.achievements).toEqual(mockResponse.data.achievements);
      expect(state.error).toBeNull();
    });

    it('should handle fetch achievements error', async () => {
      mockedAxios.get = vi.fn().mockRejectedValue(new Error('Achievements not found'));

      await store.dispatch(fetchAchievements());
      const state = store.getState().progress;

      expect(state.loading).toBe(false);
      expect(state.error).toBe('Achievements not found');
    });
  });

  describe('fetchProgressHistory', () => {
    it('should fetch progress history successfully', async () => {
      const mockResponse = {
        data: {
          history: [
            {
              date: '2025-12-06',
              exercises_completed: 1,
              time_spent_seconds: 1800,
              average_grade: 95,
              streak: 7,
              achievements_unlocked: 0,
            },
            {
              date: '2025-12-05',
              exercises_completed: 1,
              time_spent_seconds: 2100,
              average_grade: 88,
              streak: 6,
              achievements_unlocked: 1,
            },
          ],
          start_date: '2025-11-07',
          end_date: '2025-12-06',
          total_days: 30,
        },
      };

      mockedAxios.get = vi.fn().mockResolvedValue(mockResponse);

      await store.dispatch(fetchProgressHistory({ days: 30 }));
      const state = store.getState().progress;

      expect(state.loading).toBe(false);
      expect(state.history).toEqual(mockResponse.data.history);
      expect(state.error).toBeNull();
    });

    it('should handle empty history', async () => {
      const mockResponse = {
        data: {
          history: [],
          start_date: '2025-12-06',
          end_date: '2025-12-06',
          total_days: 1,
        },
      };

      mockedAxios.get = vi.fn().mockResolvedValue(mockResponse);

      await store.dispatch(fetchProgressHistory({ days: 1 }));
      const state = store.getState().progress;

      expect(state.history).toEqual([]);
    });

    it('should handle custom date range', async () => {
      const mockResponse = {
        data: {
          history: [{ date: '2025-12-05', exercises_completed: 1 }],
          start_date: '2025-12-01',
          end_date: '2025-12-05',
          total_days: 5,
        },
      };

      mockedAxios.get = vi.fn().mockResolvedValue(mockResponse);

      await store.dispatch(
        fetchProgressHistory({
          startDate: '2025-12-01',
          endDate: '2025-12-05',
        })
      );
      const state = store.getState().progress;

      expect(state.history).toEqual(mockResponse.data.history);
    });
  });

  describe('fetchStatistics', () => {
    it('should fetch statistics successfully', async () => {
      const mockResponse = {
        data: {
          average_grade: 87.5,
          average_time_per_exercise: 1800,
          total_hints_requested: 5,
          exercises_by_difficulty: {
            easy: 10,
            medium: 20,
            hard: 12,
          },
          exercises_by_type: {
            algorithm: 25,
            debugging: 10,
            practical: 7,
          },
          recent_performance_trend: [
            { date: '2025-12-01', grade: 85 },
            { date: '2025-12-02', grade: 90 },
            { date: '2025-12-03', grade: 88 },
          ],
          period: 'weekly',
        },
      };

      mockedAxios.get = vi.fn().mockResolvedValue(mockResponse);

      await store.dispatch(fetchStatistics({ period: 'weekly' }));
      const state = store.getState().progress;

      expect(state.loading).toBe(false);
      expect(state.statistics).toEqual(mockResponse.data);
      expect(state.error).toBeNull();
    });

    it('should handle fetch statistics error', async () => {
      mockedAxios.get = vi.fn().mockRejectedValue(new Error('Statistics unavailable'));

      await store.dispatch(fetchStatistics({ period: 'monthly' }));
      const state = store.getState().progress;

      expect(state.loading).toBe(false);
      expect(state.error).toBe('Statistics unavailable');
    });
  });

  describe('fetchBadges', () => {
    it('should fetch badges successfully', async () => {
      const mockResponse = {
        data: {
          badges: [
            {
              id: 1,
              type: 'streak_7',
              name: '7 Day Streak Badge',
              description: 'Awarded for 7 consecutive days',
              icon: 'fire',
              earned: true,
              earned_at: '2025-12-05',
              category: 'streak',
              points: 50,
              rarity: 'rare',
            },
            {
              id: 2,
              type: 'streak_30',
              name: '30 Day Streak Badge',
              description: 'Awarded for 30 consecutive days',
              icon: 'trophy',
              earned: false,
              category: 'streak',
              points: 200,
              rarity: 'epic',
            },
          ],
          total_earned: 1,
          total_available: 2,
          points_earned: 50,
        },
      };

      mockedAxios.get = vi.fn().mockResolvedValue(mockResponse);

      await store.dispatch(fetchBadges());
      const state = store.getState().progress;

      expect(state.loading).toBe(false);
      expect(state.badges).toEqual(mockResponse.data.badges);
      expect(state.error).toBeNull();
    });

    it('should handle fetch badges error', async () => {
      mockedAxios.get = vi.fn().mockRejectedValue(new Error('Badges not available'));

      await store.dispatch(fetchBadges());
      const state = store.getState().progress;

      expect(state.loading).toBe(false);
      expect(state.error).toBe('Badges not available');
    });
  });

  describe('fetchSkillLevels', () => {
    it('should fetch skill levels successfully', async () => {
      const mockResponse = {
        data: {
          skill_levels: [
            {
              topic: 'python',
              level: 'intermediate',
              exercises_completed: 25,
              average_grade: 87.5,
              total_time_spent_seconds: 45000,
              level_updated_at: '2025-12-05',
              previous_level: 'beginner',
            },
            {
              topic: 'javascript',
              level: 'beginner',
              exercises_completed: 8,
              average_grade: 75,
              total_time_spent_seconds: 14400,
              level_updated_at: '2025-12-02',
              previous_level: null,
            },
          ],
        },
      };

      mockedAxios.get = vi.fn().mockResolvedValue(mockResponse);

      await store.dispatch(fetchSkillLevels());
      const state = store.getState().progress;

      expect(state.loading).toBe(false);
      expect(state.skillLevels).toEqual(mockResponse.data.skill_levels);
      expect(state.error).toBeNull();
    });

    it('should handle empty skill levels', async () => {
      const mockResponse = {
        data: {
          skill_levels: [],
        },
      };

      mockedAxios.get = vi.fn().mockResolvedValue(mockResponse);

      await store.dispatch(fetchSkillLevels());
      const state = store.getState().progress;

      expect(state.skillLevels).toEqual([]);
    });
  });

  describe('exportProgressData', () => {
    it('should export progress data as JSON', async () => {
      const mockResponse = {
        data: {
          user_id: 1,
          export_date: '2025-12-06T10:00:00Z',
          progress_metrics: {
            exercises_completed: 42,
            current_streak: 7,
          },
          achievements: [],
          exercise_history: [],
          statistics: {},
        },
      };

      mockedAxios.get = vi.fn().mockResolvedValue(mockResponse);

      await store.dispatch(exportProgressData({ format: 'json' }));
      const state = store.getState().progress;

      expect(state.loading).toBe(false);
      expect(state.error).toBeNull();
      expect(mockedAxios.get).toHaveBeenCalled();
    });

    it('should export progress data as CSV', async () => {
      const mockResponse = {
        data: 'date,exercises_completed,streak\n2025-12-06,1,7\n',
      };

      mockedAxios.get = vi.fn().mockResolvedValue(mockResponse);

      await store.dispatch(exportProgressData({ format: 'csv' }));
      const state = store.getState().progress;

      expect(state.loading).toBe(false);
      expect(state.error).toBeNull();
    });

    it('should handle export error', async () => {
      mockedAxios.get = vi.fn().mockRejectedValue(new Error('Export failed'));

      await store.dispatch(exportProgressData({ format: 'json' }));
      const state = store.getState().progress;

      expect(state.loading).toBe(false);
      expect(state.error).toBe('Export failed');
    });
  });

  describe('integration workflow', () => {
    it('should handle complete progress workflow: fetch metrics -> achievements -> history', async () => {
      // Step 1: Fetch progress metrics
      const metricsResponse = {
        data: {
          exercises_completed: 42,
          current_streak: 7,
          longest_streak: 14,
          total_time_spent_seconds: 86400,
          average_grade: 87.5,
        },
      };

      mockedAxios.get = vi.fn().mockResolvedValue(metricsResponse);
      await store.dispatch(fetchProgressMetrics());

      let state = store.getState().progress;
      expect(state.metrics).toEqual(metricsResponse.data);

      // Step 2: Fetch achievements
      const achievementsResponse = {
        data: {
          achievements: [
            { id: 1, name: '7 Day Streak', unlocked: true, points: 50 },
          ],
          total_points: 50,
          unlocked_count: 1,
          total_count: 10,
        },
      };

      mockedAxios.get = vi.fn().mockResolvedValue(achievementsResponse);
      await store.dispatch(fetchAchievements());

      state = store.getState().progress;
      expect(state.achievements).toEqual(achievementsResponse.data.achievements);

      // Step 3: Fetch history
      const historyResponse = {
        data: {
          history: [
            { date: '2025-12-06', exercises_completed: 1, streak: 7 },
          ],
          start_date: '2025-11-07',
          end_date: '2025-12-06',
          total_days: 30,
        },
      };

      mockedAxios.get = vi.fn().mockResolvedValue(historyResponse);
      await store.dispatch(fetchProgressHistory({ days: 30 }));

      state = store.getState().progress;
      expect(state.history).toEqual(historyResponse.data.history);
    });
  });

  describe('error handling', () => {
    it('should handle API errors with proper messages', async () => {
      const errorResponse = {
        response: {
          data: {
            message: 'User not found',
          },
        },
      };

      mockedAxios.get = vi.fn().mockRejectedValue(errorResponse);

      await store.dispatch(fetchProgressMetrics());
      const state = store.getState().progress;

      expect(state.error).toBeTruthy();
    });

    it('should handle network errors gracefully', async () => {
      mockedAxios.get = vi.fn().mockRejectedValue(new Error('Network error'));

      await store.dispatch(fetchProgressMetrics());
      const state = store.getState().progress;

      expect(state.error).toBe('Network error');
      expect(state.loading).toBe(false);
    });
  });
});
