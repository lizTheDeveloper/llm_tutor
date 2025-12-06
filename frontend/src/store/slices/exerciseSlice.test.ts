/**
 * Test Suite for Exercise Redux Slice
 *
 * Test Strategy:
 * - Test all Redux state management for exercise functionality
 * - Test async thunks for D1 API integration (daily exercise, submission, hints, etc.)
 * - Test state updates for loading, error, and success cases
 * - Mock API calls to test integration without external dependencies
 * - Test exercise workflow: fetch -> submit -> evaluate -> complete
 * - Integration tests over unit tests - test real code paths users will execute
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';
import exerciseReducer, {
  fetchDailyExercise,
  fetchExercise,
  fetchExerciseHistory,
  submitExercise,
  requestHint,
  skipExercise,
  generateExercise,
  setCurrentExercise,
  clearError,
  saveDraftSolution,
  ExerciseState,
} from './exerciseSlice';
import { configureStore } from '@reduxjs/toolkit';
import axios from 'axios';

// Mock axios
vi.mock('axios');
const mockedAxios = vi.mocked(axios, true);

// Mock localStorage
const localStorageMock = (() => {
  let store: Record<string, string> = {};
  return {
    getItem: (key: string) => store[key] || null,
    setItem: (key: string, value: string) => {
      store[key] = value;
    },
    removeItem: (key: string) => {
      delete store[key];
    },
    clear: () => {
      store = {};
    },
  };
})();

Object.defineProperty(window, 'localStorage', {
  value: localStorageMock,
});

describe('exerciseSlice', () => {
  let store: ReturnType<typeof configureStore>;

  beforeEach(() => {
    // Reset mocks
    vi.clearAllMocks();
    localStorageMock.clear();

    // Create fresh store for each test
    store = configureStore({
      reducer: {
        exercise: exerciseReducer,
      },
    });

    // Mock axios create to return mocked axios instance
    mockedAxios.create = vi.fn(() => mockedAxios as any);
  });

  describe('initial state', () => {
    it('should have correct initial state', () => {
      const state = store.getState().exercise;

      expect(state.dailyExercise).toBeNull();
      expect(state.currentExercise).toBeNull();
      expect(state.exerciseHistory).toEqual([]);
      expect(state.loading).toBe(false);
      expect(state.submitting).toBe(false);
      expect(state.error).toBeNull();
      expect(state.draftSolution).toBeNull();
      expect(state.hints).toEqual([]);
      expect(state.hintsUsed).toBe(0);
      expect(state.submissionResult).toBeNull();
    });
  });

  describe('synchronous actions', () => {
    it('should set current exercise', () => {
      const exercise = {
        id: 1,
        title: 'Test Exercise',
        description: 'Test description',
        instructions: 'Test instructions',
        difficulty: 'medium',
        programming_language: 'python',
      };

      store.dispatch(setCurrentExercise(exercise as any));
      const state = store.getState().exercise;

      expect(state.currentExercise).toEqual(exercise);
    });

    it('should clear error', () => {
      const initialState: ExerciseState = {
        dailyExercise: null,
        currentExercise: null,
        exerciseHistory: [],
        loading: false,
        submitting: false,
        error: 'Test error',
        draftSolution: null,
        hints: [],
        hintsUsed: 0,
        submissionResult: null,
      };

      const state = exerciseReducer(initialState, clearError());

      expect(state.error).toBeNull();
    });

    it('should save draft solution to state and localStorage', () => {
      const exerciseId = 1;
      const solution = 'def hello():\n    return "world"';

      store.dispatch(saveDraftSolution({ exerciseId, solution }));
      const state = store.getState().exercise;

      expect(state.draftSolution).toEqual({ exerciseId, solution });
      expect(localStorageMock.getItem(`exercise_draft_${exerciseId}`)).toBe(solution);
    });

    it('should remove draft from localStorage when solution is empty', () => {
      const exerciseId = 1;
      const solution = '';

      // First save a draft
      localStorageMock.setItem(`exercise_draft_${exerciseId}`, 'some code');

      store.dispatch(saveDraftSolution({ exerciseId, solution }));

      expect(localStorageMock.getItem(`exercise_draft_${exerciseId}`)).toBeNull();
    });
  });

  describe('fetchDailyExercise', () => {
    it('should fetch daily exercise successfully', async () => {
      const mockResponse = {
        data: {
          exercise: {
            id: 1,
            title: 'Daily Coding Challenge',
            description: 'Implement a function to reverse a string',
            instructions: 'Write a function that takes a string and returns it reversed',
            starter_code: 'def reverse_string(s):\n    pass',
            exercise_type: 'algorithm',
            difficulty: 'medium',
            programming_language: 'python',
            topics: 'strings, algorithms',
            test_cases: 'assert reverse_string("hello") == "olleh"',
            generated_by_ai: true,
          },
          user_exercise_id: 42,
          status: 'in_progress',
          hints_used: 0,
          is_new: true,
        },
      };

      mockedAxios.get = vi.fn().mockResolvedValue(mockResponse);

      await store.dispatch(fetchDailyExercise());
      const state = store.getState().exercise;

      expect(state.loading).toBe(false);
      expect(state.dailyExercise).toEqual(mockResponse.data);
      expect(state.currentExercise).toEqual(mockResponse.data.exercise);
      expect(state.hintsUsed).toBe(0);
      expect(state.error).toBeNull();
      expect(mockedAxios.get).toHaveBeenCalled();
    });

    it('should handle fetch daily exercise error', async () => {
      const mockError = new Error('Network error');
      mockedAxios.get = vi.fn().mockRejectedValue(mockError);

      await store.dispatch(fetchDailyExercise());
      const state = store.getState().exercise;

      expect(state.loading).toBe(false);
      expect(state.dailyExercise).toBeNull();
      expect(state.error).toBe('Network error');
    });

    it('should set loading state while fetching', async () => {
      const mockPromise = new Promise((resolve) => setTimeout(resolve, 100));
      mockedAxios.get = vi.fn().mockReturnValue(mockPromise);

      const dispatchPromise = store.dispatch(fetchDailyExercise());
      const state = store.getState().exercise;

      expect(state.loading).toBe(true);

      await dispatchPromise;
    });
  });

  describe('fetchExercise', () => {
    it('should fetch specific exercise by ID', async () => {
      const mockResponse = {
        data: {
          id: 5,
          title: 'Binary Search Implementation',
          description: 'Implement binary search algorithm',
          instructions: 'Write an efficient binary search',
          difficulty: 'hard',
          programming_language: 'javascript',
          exercise_type: 'algorithm',
          starter_code: 'function binarySearch(arr, target) {\n  // your code\n}',
          topics: 'algorithms, search',
        },
      };

      mockedAxios.get = vi.fn().mockResolvedValue(mockResponse);

      await store.dispatch(fetchExercise(5));
      const state = store.getState().exercise;

      expect(state.loading).toBe(false);
      expect(state.currentExercise).toEqual(mockResponse.data);
      expect(state.error).toBeNull();
      expect(mockedAxios.get).toHaveBeenCalled();
    });

    it('should handle fetch exercise error', async () => {
      mockedAxios.get = vi.fn().mockRejectedValue(new Error('Exercise not found'));

      await store.dispatch(fetchExercise(999));
      const state = store.getState().exercise;

      expect(state.loading).toBe(false);
      expect(state.error).toBe('Exercise not found');
    });
  });

  describe('fetchExerciseHistory', () => {
    it('should fetch exercise history with pagination', async () => {
      const mockResponse = {
        data: {
          exercises: [
            { id: 1, title: 'Exercise 1', status: 'completed', completed_at: '2025-12-05' },
            { id: 2, title: 'Exercise 2', status: 'completed', completed_at: '2025-12-04' },
          ],
          total: 10,
          limit: 20,
          offset: 0,
          has_more: false,
        },
      };

      mockedAxios.get = vi.fn().mockResolvedValue(mockResponse);

      await store.dispatch(fetchExerciseHistory({ limit: 20, offset: 0 }));
      const state = store.getState().exercise;

      expect(state.loading).toBe(false);
      expect(state.exerciseHistory).toEqual(mockResponse.data.exercises);
      expect(state.error).toBeNull();
      expect(mockedAxios.get).toHaveBeenCalled();
    });

    it('should handle empty history', async () => {
      const mockResponse = {
        data: {
          exercises: [],
          total: 0,
          limit: 20,
          offset: 0,
          has_more: false,
        },
      };

      mockedAxios.get = vi.fn().mockResolvedValue(mockResponse);

      await store.dispatch(fetchExerciseHistory({ limit: 20, offset: 0 }));
      const state = store.getState().exercise;

      expect(state.exerciseHistory).toEqual([]);
    });
  });

  describe('submitExercise', () => {
    it('should submit exercise solution successfully', async () => {
      const mockResponse = {
        data: {
          grade: 95.5,
          feedback: 'Great work! Your solution is efficient.',
          strengths: ['Clean code', 'Good algorithm choice'],
          improvements: ['Could add more error handling'],
          status: 'completed',
          hints_used: 1,
          submission_count: 2,
        },
      };

      mockedAxios.post = vi.fn().mockResolvedValue(mockResponse);

      const payload = {
        exerciseId: 1,
        solution: 'def reverse_string(s):\n    return s[::-1]',
        timeSpentSeconds: 300,
      };

      await store.dispatch(submitExercise(payload));
      const state = store.getState().exercise;

      expect(state.submitting).toBe(false);
      expect(state.submissionResult).toEqual(mockResponse.data);
      expect(state.error).toBeNull();
      expect(mockedAxios.post).toHaveBeenCalled();
    });

    it('should handle submission error', async () => {
      mockedAxios.post = vi.fn().mockRejectedValue(new Error('Submission failed'));

      const payload = {
        exerciseId: 1,
        solution: 'incomplete code',
        timeSpentSeconds: 100,
      };

      await store.dispatch(submitExercise(payload));
      const state = store.getState().exercise;

      expect(state.submitting).toBe(false);
      expect(state.submissionResult).toBeNull();
      expect(state.error).toBe('Submission failed');
    });

    it('should set submitting state during submission', async () => {
      const mockPromise = new Promise((resolve) => setTimeout(resolve, 100));
      mockedAxios.post = vi.fn().mockReturnValue(mockPromise);

      const dispatchPromise = store.dispatch(
        submitExercise({
          exerciseId: 1,
          solution: 'code',
          timeSpentSeconds: 100,
        })
      );
      const state = store.getState().exercise;

      expect(state.submitting).toBe(true);

      await dispatchPromise;
    });

    it('should clear draft solution after successful submission', async () => {
      const exerciseId = 1;
      const mockResponse = {
        data: {
          grade: 90,
          feedback: 'Good work',
          strengths: [],
          improvements: [],
          status: 'completed',
          hints_used: 0,
          submission_count: 1,
        },
      };

      mockedAxios.post = vi.fn().mockResolvedValue(mockResponse);

      // Set a draft first
      localStorageMock.setItem(`exercise_draft_${exerciseId}`, 'draft code');

      await store.dispatch(
        submitExercise({
          exerciseId,
          solution: 'final solution',
          timeSpentSeconds: 200,
        })
      );

      // Draft should be removed
      expect(localStorageMock.getItem(`exercise_draft_${exerciseId}`)).toBeNull();
    });
  });

  describe('requestHint', () => {
    it('should request hint successfully', async () => {
      const mockResponse = {
        data: {
          hint: 'Try using Python slicing with negative step',
          hints_used: 1,
          hints_remaining: 2,
          difficulty_level: 1,
        },
      };

      mockedAxios.post = vi.fn().mockResolvedValue(mockResponse);

      await store.dispatch(
        requestHint({
          exerciseId: 1,
          context: 'Stuck on string reversal',
          currentCode: 'def reverse_string(s):',
        })
      );
      const state = store.getState().exercise;

      expect(state.hints).toHaveLength(1);
      expect(state.hints[0]).toBe('Try using Python slicing with negative step');
      expect(state.hintsUsed).toBe(1);
      expect(state.error).toBeNull();
      expect(mockedAxios.post).toHaveBeenCalled();
    });

    it('should accumulate multiple hints', async () => {
      const mockResponse1 = {
        data: { hint: 'First hint', hints_used: 1 },
      };
      const mockResponse2 = {
        data: { hint: 'Second hint', hints_used: 2 },
      };

      mockedAxios.post = vi.fn()
        .mockResolvedValueOnce(mockResponse1)
        .mockResolvedValueOnce(mockResponse2);

      await store.dispatch(requestHint({ exerciseId: 1 }));
      await store.dispatch(requestHint({ exerciseId: 1 }));

      const state = store.getState().exercise;

      expect(state.hints).toHaveLength(2);
      expect(state.hints).toEqual(['First hint', 'Second hint']);
      expect(state.hintsUsed).toBe(2);
    });

    it('should handle hint request error', async () => {
      mockedAxios.post = vi.fn().mockRejectedValue(new Error('No hints available'));

      await store.dispatch(requestHint({ exerciseId: 1 }));
      const state = store.getState().exercise;

      expect(state.error).toBe('No hints available');
      expect(state.hints).toEqual([]);
    });
  });

  describe('skipExercise', () => {
    it('should skip exercise successfully', async () => {
      const mockResponse = {
        data: {
          exercise_id: 1,
          user_exercise_id: 42,
          status: 'skipped',
          skipped_at: '2025-12-06T10:00:00Z',
        },
      };

      mockedAxios.post = vi.fn().mockResolvedValue(mockResponse);

      await store.dispatch(skipExercise(1));
      const state = store.getState().exercise;

      expect(state.error).toBeNull();
      expect(mockedAxios.post).toHaveBeenCalled();
    });

    it('should clear draft when skipping', async () => {
      const exerciseId = 1;
      const mockResponse = {
        data: { exercise_id: exerciseId, status: 'skipped' },
      };

      mockedAxios.post = vi.fn().mockResolvedValue(mockResponse);

      // Set a draft
      localStorageMock.setItem(`exercise_draft_${exerciseId}`, 'draft code');

      await store.dispatch(skipExercise(exerciseId));

      expect(localStorageMock.getItem(`exercise_draft_${exerciseId}`)).toBeNull();
    });
  });

  describe('generateExercise', () => {
    it('should generate custom exercise successfully', async () => {
      const mockResponse = {
        data: {
          id: 10,
          title: 'Custom Algorithm Challenge',
          description: 'Generated exercise',
          difficulty: 'medium',
          programming_language: 'python',
          exercise_type: 'algorithm',
          generated_by_ai: true,
        },
      };

      mockedAxios.post = vi.fn().mockResolvedValue(mockResponse);

      await store.dispatch(
        generateExercise({
          topic: 'binary trees',
          difficulty: 'medium',
        })
      );
      const state = store.getState().exercise;

      expect(state.currentExercise).toEqual(mockResponse.data);
      expect(state.error).toBeNull();
      expect(mockedAxios.post).toHaveBeenCalled();
    });

    it('should handle generate exercise error', async () => {
      mockedAxios.post = vi.fn().mockRejectedValue(new Error('Generation failed'));

      await store.dispatch(generateExercise({ topic: 'invalid' }));
      const state = store.getState().exercise;

      expect(state.error).toBe('Generation failed');
    });
  });

  describe('integration workflow', () => {
    it('should handle complete exercise workflow: fetch -> hint -> submit -> complete', async () => {
      // Step 1: Fetch daily exercise
      const dailyResponse = {
        data: {
          exercise: {
            id: 1,
            title: 'String Reversal',
            difficulty: 'easy',
            programming_language: 'python',
          },
          user_exercise_id: 42,
          status: 'in_progress',
          hints_used: 0,
          is_new: true,
        },
      };

      mockedAxios.get = vi.fn().mockResolvedValue(dailyResponse);
      await store.dispatch(fetchDailyExercise());

      let state = store.getState().exercise;
      expect(state.currentExercise?.id).toBe(1);

      // Step 2: Request a hint
      const hintResponse = {
        data: { hint: 'Use slicing', hints_used: 1 },
      };

      mockedAxios.post = vi.fn().mockResolvedValue(hintResponse);
      await store.dispatch(requestHint({ exerciseId: 1 }));

      state = store.getState().exercise;
      expect(state.hints).toHaveLength(1);
      expect(state.hintsUsed).toBe(1);

      // Step 3: Submit solution
      const submitResponse = {
        data: {
          grade: 100,
          feedback: 'Perfect!',
          strengths: ['Correct', 'Efficient'],
          improvements: [],
          status: 'completed',
          hints_used: 1,
          submission_count: 1,
        },
      };

      mockedAxios.post = vi.fn().mockResolvedValue(submitResponse);
      await store.dispatch(
        submitExercise({
          exerciseId: 1,
          solution: 'def reverse(s): return s[::-1]',
          timeSpentSeconds: 600,
        })
      );

      state = store.getState().exercise;
      expect(state.submissionResult?.grade).toBe(100);
      expect(state.submissionResult?.status).toBe('completed');
    });
  });

  describe('error handling', () => {
    it('should handle API errors with proper messages', async () => {
      const errorResponse = {
        response: {
          data: {
            message: 'Exercise already completed',
          },
        },
      };

      mockedAxios.get = vi.fn().mockRejectedValue(errorResponse);

      await store.dispatch(fetchDailyExercise());
      const state = store.getState().exercise;

      expect(state.error).toBeTruthy();
    });

    it('should handle network errors gracefully', async () => {
      mockedAxios.get = vi.fn().mockRejectedValue(new Error('Network error'));

      await store.dispatch(fetchDailyExercise());
      const state = store.getState().exercise;

      expect(state.error).toBe('Network error');
      expect(state.loading).toBe(false);
    });
  });
});
