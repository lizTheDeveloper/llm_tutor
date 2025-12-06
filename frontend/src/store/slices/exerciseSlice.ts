/**
 * Redux slice for exercise management.
 *
 * Manages:
 * - Daily exercise fetching and generation
 * - Exercise history and pagination
 * - Solution submission and evaluation
 * - Hint requests
 * - Draft solution persistence (localStorage)
 * - Exercise workflow state
 */

import { createSlice, createAsyncThunk, PayloadAction } from '@reduxjs/toolkit';
import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

// API client helper - returns auth headers
const getAuthHeaders = () => {
  const token = localStorage.getItem('access_token');
  return {
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
  };
};

// ===================================================================
// TYPE DEFINITIONS
// ===================================================================

export interface Exercise {
  id: number;
  title: string;
  description: string;
  instructions: string;
  starter_code?: string;
  exercise_type: string;
  difficulty: string;
  programming_language: string;
  topics?: string;
  test_cases?: string;
  generated_by_ai: boolean;
  created_at?: string;
}

export interface DailyExercise {
  exercise: Exercise;
  user_exercise_id: number;
  status: string;
  hints_used: number;
  is_new: boolean;
  started_at?: string;
}

export interface SubmissionResult {
  grade: number;
  feedback: string;
  strengths: string[];
  improvements: string[];
  status: string;
  hints_used: number;
  submission_count: number;
}

export interface HintResponse {
  hint: string;
  hints_used: number;
  hints_remaining?: number;
  difficulty_level: number;
}

export interface ExerciseHistoryItem {
  id: number;
  title: string;
  status: string;
  difficulty: string;
  programming_language: string;
  completed_at?: string;
  grade?: number;
}

export interface DraftSolution {
  exerciseId: number;
  solution: string;
}

export interface ExerciseState {
  dailyExercise: DailyExercise | null;
  currentExercise: Exercise | null;
  exerciseHistory: ExerciseHistoryItem[];
  loading: boolean;
  submitting: boolean;
  error: string | null;
  draftSolution: DraftSolution | null;
  hints: string[];
  hintsUsed: number;
  submissionResult: SubmissionResult | null;
}

// ===================================================================
// ASYNC THUNKS
// ===================================================================

/**
 * Fetch today's daily exercise.
 * Generates a new one if not already created.
 */
export const fetchDailyExercise = createAsyncThunk(
  'exercise/fetchDailyExercise',
  async (_, { rejectWithValue }) => {
    try {
      const response = await axios.get(`${API_BASE_URL}/api/exercises/daily`, getAuthHeaders());
      return response.data;
    } catch (error: any) {
      return rejectWithValue(error.response?.data?.message || error.message);
    }
  }
);

/**
 * Fetch a specific exercise by ID.
 */
export const fetchExercise = createAsyncThunk(
  'exercise/fetchExercise',
  async (exerciseId: number, { rejectWithValue }) => {
    try {
      const response = await axios.get(`${API_BASE_URL}/api/exercises/${exerciseId}`, getAuthHeaders());
      return response.data;
    } catch (error: any) {
      return rejectWithValue(error.response?.data?.message || error.message);
    }
  }
);

/**
 * Fetch exercise history with pagination and filters.
 */
export const fetchExerciseHistory = createAsyncThunk(
  'exercise/fetchExerciseHistory',
  async (
    params: {
      limit?: number;
      offset?: number;
      status?: string;
      difficulty?: string;
      programming_language?: string;
    },
    { rejectWithValue }
  ) => {
    try {
      const response = await axios.get(
        `${API_BASE_URL}/api/exercises/history`,
        { ...getAuthHeaders(), params }
      );
      return response.data;
    } catch (error: any) {
      return rejectWithValue(error.response?.data?.message || error.message);
    }
  }
);

/**
 * Submit exercise solution for evaluation.
 */
export const submitExercise = createAsyncThunk(
  'exercise/submitExercise',
  async (
    payload: {
      exerciseId: number;
      solution: string;
      timeSpentSeconds?: number;
    },
    { rejectWithValue }
  ) => {
    try {
      const response = await axios.post(
        `${API_BASE_URL}/api/exercises/${payload.exerciseId}/submit`,
        {
          solution: payload.solution,
          time_spent_seconds: payload.timeSpentSeconds,
        },
        getAuthHeaders()
      );

      // Clear draft solution after successful submission
      localStorage.removeItem(`exercise_draft_${payload.exerciseId}`);

      return response.data;
    } catch (error: any) {
      return rejectWithValue(error.response?.data?.message || error.message);
    }
  }
);

/**
 * Request a hint for the current exercise.
 */
export const requestHint = createAsyncThunk(
  'exercise/requestHint',
  async (
    payload: {
      exerciseId: number;
      context?: string;
      currentCode?: string;
    },
    { rejectWithValue }
  ) => {
    try {
      const response = await axios.post(
        `${API_BASE_URL}/api/exercises/${payload.exerciseId}/hint`,
        {
          context: payload.context,
          current_code: payload.currentCode,
        },
        getAuthHeaders()
      );
      return response.data;
    } catch (error: any) {
      return rejectWithValue(error.response?.data?.message || error.message);
    }
  }
);

/**
 * Skip the current exercise.
 */
export const skipExercise = createAsyncThunk(
  'exercise/skipExercise',
  async (exerciseId: number, { rejectWithValue }) => {
    try {
      const response = await axios.post(
        `${API_BASE_URL}/api/exercises/${exerciseId}/skip`,
        {},
        getAuthHeaders()
      );

      // Clear draft solution when skipping
      localStorage.removeItem(`exercise_draft_${exerciseId}`);

      return response.data;
    } catch (error: any) {
      return rejectWithValue(error.response?.data?.message || error.message);
    }
  }
);

/**
 * Generate a custom exercise with specific parameters.
 */
export const generateExercise = createAsyncThunk(
  'exercise/generateExercise',
  async (
    params: {
      topic?: string;
      difficulty?: string;
      exercise_type?: string;
    },
    { rejectWithValue }
  ) => {
    try {
      const response = await axios.post(
        `${API_BASE_URL}/api/exercises/generate`,
        params,
        getAuthHeaders()
      );
      return response.data;
    } catch (error: any) {
      return rejectWithValue(error.response?.data?.message || error.message);
    }
  }
);

// ===================================================================
// SLICE
// ===================================================================

const initialState: ExerciseState = {
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
};

const exerciseSlice = createSlice({
  name: 'exercise',
  initialState,
  reducers: {
    /**
     * Set the current exercise being worked on.
     */
    setCurrentExercise: (state, action: PayloadAction<Exercise>) => {
      state.currentExercise = action.payload;
      state.hints = [];
      state.hintsUsed = 0;
      state.submissionResult = null;
      state.error = null;
    },

    /**
     * Clear any error messages.
     */
    clearError: (state) => {
      state.error = null;
    },

    /**
     * Save draft solution to state and localStorage.
     */
    saveDraftSolution: (state, action: PayloadAction<DraftSolution>) => {
      const { exerciseId, solution } = action.payload;
      state.draftSolution = { exerciseId, solution };

      if (solution && solution.trim()) {
        localStorage.setItem(`exercise_draft_${exerciseId}`, solution);
      } else {
        localStorage.removeItem(`exercise_draft_${exerciseId}`);
      }
    },

    /**
     * Clear submission result.
     */
    clearSubmissionResult: (state) => {
      state.submissionResult = null;
    },

    /**
     * Reset exercise state.
     */
    resetExerciseState: (state) => {
      state.currentExercise = null;
      state.hints = [];
      state.hintsUsed = 0;
      state.submissionResult = null;
      state.draftSolution = null;
      state.error = null;
    },
  },
  extraReducers: (builder) => {
    // ============ fetchDailyExercise ============
    builder.addCase(fetchDailyExercise.pending, (state) => {
      state.loading = true;
      state.error = null;
    });
    builder.addCase(fetchDailyExercise.fulfilled, (state, action) => {
      state.loading = false;
      state.dailyExercise = action.payload;
      state.currentExercise = action.payload.exercise;
      state.hintsUsed = action.payload.hints_used;
      state.hints = [];
      state.submissionResult = null;
    });
    builder.addCase(fetchDailyExercise.rejected, (state, action) => {
      state.loading = false;
      state.error = action.payload as string;
    });

    // ============ fetchExercise ============
    builder.addCase(fetchExercise.pending, (state) => {
      state.loading = true;
      state.error = null;
    });
    builder.addCase(fetchExercise.fulfilled, (state, action) => {
      state.loading = false;
      state.currentExercise = action.payload;
      state.hints = [];
      state.hintsUsed = 0;
      state.submissionResult = null;
    });
    builder.addCase(fetchExercise.rejected, (state, action) => {
      state.loading = false;
      state.error = action.payload as string;
    });

    // ============ fetchExerciseHistory ============
    builder.addCase(fetchExerciseHistory.pending, (state) => {
      state.loading = true;
      state.error = null;
    });
    builder.addCase(fetchExerciseHistory.fulfilled, (state, action) => {
      state.loading = false;
      state.exerciseHistory = action.payload.exercises;
    });
    builder.addCase(fetchExerciseHistory.rejected, (state, action) => {
      state.loading = false;
      state.error = action.payload as string;
    });

    // ============ submitExercise ============
    builder.addCase(submitExercise.pending, (state) => {
      state.submitting = true;
      state.error = null;
    });
    builder.addCase(submitExercise.fulfilled, (state, action) => {
      state.submitting = false;
      state.submissionResult = action.payload;
      state.draftSolution = null;
    });
    builder.addCase(submitExercise.rejected, (state, action) => {
      state.submitting = false;
      state.error = action.payload as string;
    });

    // ============ requestHint ============
    builder.addCase(requestHint.pending, (state) => {
      state.loading = true;
      state.error = null;
    });
    builder.addCase(requestHint.fulfilled, (state, action: PayloadAction<HintResponse>) => {
      state.loading = false;
      state.hints.push(action.payload.hint);
      state.hintsUsed = action.payload.hints_used;
    });
    builder.addCase(requestHint.rejected, (state, action) => {
      state.loading = false;
      state.error = action.payload as string;
    });

    // ============ skipExercise ============
    builder.addCase(skipExercise.pending, (state) => {
      state.loading = true;
      state.error = null;
    });
    builder.addCase(skipExercise.fulfilled, (state) => {
      state.loading = false;
      state.draftSolution = null;
      state.currentExercise = null;
      state.hints = [];
      state.hintsUsed = 0;
    });
    builder.addCase(skipExercise.rejected, (state, action) => {
      state.loading = false;
      state.error = action.payload as string;
    });

    // ============ generateExercise ============
    builder.addCase(generateExercise.pending, (state) => {
      state.loading = true;
      state.error = null;
    });
    builder.addCase(generateExercise.fulfilled, (state, action) => {
      state.loading = false;
      state.currentExercise = action.payload;
      state.hints = [];
      state.hintsUsed = 0;
      state.submissionResult = null;
    });
    builder.addCase(generateExercise.rejected, (state, action) => {
      state.loading = false;
      state.error = action.payload as string;
    });
  },
});

export const {
  setCurrentExercise,
  clearError,
  saveDraftSolution,
  clearSubmissionResult,
  resetExerciseState,
} = exerciseSlice.actions;

export default exerciseSlice.reducer;
