/**
 * Redux slice for progress tracking and achievements.
 *
 * Manages:
 * - Progress metrics (exercises completed, streaks, grades)
 * - Achievements and badges
 * - Progress history and trends
 * - Statistics and analytics
 * - Skill level tracking
 * - Data export functionality
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

export interface ProgressMetrics {
  exercises_completed: number;
  current_streak: number;
  longest_streak: number;
  total_time_spent_seconds: number;
  average_grade: number | null;
  achievements: any[];
  skill_levels: Record<string, any>;
}

export interface Achievement {
  id: number;
  name: string;
  slug: string;
  title: string;
  description: string;
  category: string;
  requirement_value?: number;
  requirement_description: string;
  icon_url?: string;
  badge_color?: string;
  points: number;
  unlocked: boolean;
  unlocked_at?: string;
  progress?: number;
  target?: number;
  progress_percentage?: number;
}

export interface ProgressHistoryEntry {
  date: string;
  exercises_completed: number;
  time_spent_seconds: number;
  average_grade: number | null;
  streak: number;
  achievements_unlocked: number;
}

export interface Statistics {
  average_grade: number;
  average_time_per_exercise: number;
  total_hints_requested: number;
  exercises_by_difficulty: Record<string, number>;
  exercises_by_type: Record<string, number>;
  recent_performance_trend: any[];
  period?: string;
}

export interface Badge {
  id: number;
  type: string;
  name: string;
  description: string;
  icon_url?: string;
  icon?: string;
  earned: boolean;
  earned_at?: string;
  category: string;
  points: number;
  rarity?: string;
}

export interface SkillLevel {
  topic: string;
  level: string;
  exercises_completed: number;
  average_grade: number | null;
  total_time_spent_seconds: number;
  level_updated_at?: string;
  previous_level?: string;
}

export interface ProgressState {
  metrics: ProgressMetrics | null;
  achievements: Achievement[];
  history: ProgressHistoryEntry[];
  statistics: Statistics | null;
  badges: Badge[];
  skillLevels: SkillLevel[];
  loading: boolean;
  error: string | null;
}

// ===================================================================
// ASYNC THUNKS
// ===================================================================

/**
 * Fetch overall progress metrics for the user.
 */
export const fetchProgressMetrics = createAsyncThunk(
  'progress/fetchProgressMetrics',
  async (_, { rejectWithValue }) => {
    try {
      const response = await axios.get(`${API_BASE_URL}/api/progress`, getAuthHeaders());
      return response.data;
    } catch (error: any) {
      return rejectWithValue(error.response?.data?.message || error.message);
    }
  }
);

/**
 * Fetch all achievements (locked and unlocked).
 */
export const fetchAchievements = createAsyncThunk(
  'progress/fetchAchievements',
  async (_, { rejectWithValue }) => {
    try {
      const response = await axios.get(`${API_BASE_URL}/api/progress/achievements`, getAuthHeaders());
      return response.data;
    } catch (error: any) {
      return rejectWithValue(error.response?.data?.message || error.message);
    }
  }
);

/**
 * Fetch progress history for a date range.
 */
export const fetchProgressHistory = createAsyncThunk(
  'progress/fetchProgressHistory',
  async (
    params: {
      days?: number;
      startDate?: string;
      endDate?: string;
    },
    { rejectWithValue }
  ) => {
    try {
      const response = await axios.get(
        `${API_BASE_URL}/api/progress/history`,
        { ...getAuthHeaders(), params }
      );
      return response.data;
    } catch (error: any) {
      return rejectWithValue(error.response?.data?.message || error.message);
    }
  }
);

/**
 * Fetch performance statistics.
 */
export const fetchStatistics = createAsyncThunk(
  'progress/fetchStatistics',
  async (
    params: {
      period?: string;
    },
    { rejectWithValue }
  ) => {
    try {
      const response = await axios.get(
        `${API_BASE_URL}/api/progress/statistics`,
        { ...getAuthHeaders(), params }
      );
      return response.data;
    } catch (error: any) {
      return rejectWithValue(error.response?.data?.message || error.message);
    }
  }
);

/**
 * Fetch badges (earned and unearned).
 */
export const fetchBadges = createAsyncThunk(
  'progress/fetchBadges',
  async (_, { rejectWithValue }) => {
    try {
      const response = await axios.get(`${API_BASE_URL}/api/progress/badges`, getAuthHeaders());
      return response.data;
    } catch (error: any) {
      return rejectWithValue(error.response?.data?.message || error.message);
    }
  }
);

/**
 * Fetch skill levels for all topics.
 */
export const fetchSkillLevels = createAsyncThunk(
  'progress/fetchSkillLevels',
  async (_, { rejectWithValue }) => {
    try {
      const response = await axios.get(`${API_BASE_URL}/api/progress/skills`, getAuthHeaders());
      return response.data;
    } catch (error: any) {
      return rejectWithValue(error.response?.data?.message || error.message);
    }
  }
);

/**
 * Export progress data in JSON or CSV format.
 */
export const exportProgressData = createAsyncThunk(
  'progress/exportProgressData',
  async (
    params: {
      format: 'json' | 'csv';
    },
    { rejectWithValue }
  ) => {
    try {
      const response = await axios.get(
        `${API_BASE_URL}/api/progress/export`,
        { ...getAuthHeaders(), params }
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

const initialState: ProgressState = {
  metrics: null,
  achievements: [],
  history: [],
  statistics: null,
  badges: [],
  skillLevels: [],
  loading: false,
  error: null,
};

const progressSlice = createSlice({
  name: 'progress',
  initialState,
  reducers: {
    /**
     * Clear any error messages.
     */
    clearError: (state) => {
      state.error = null;
    },

    /**
     * Reset progress state.
     */
    resetProgressState: (state) => {
      state.metrics = null;
      state.achievements = [];
      state.history = [];
      state.statistics = null;
      state.badges = [];
      state.skillLevels = [];
      state.error = null;
    },
  },
  extraReducers: (builder) => {
    // ============ fetchProgressMetrics ============
    builder.addCase(fetchProgressMetrics.pending, (state) => {
      state.loading = true;
      state.error = null;
    });
    builder.addCase(fetchProgressMetrics.fulfilled, (state, action) => {
      state.loading = false;
      state.metrics = action.payload;
    });
    builder.addCase(fetchProgressMetrics.rejected, (state, action) => {
      state.loading = false;
      state.error = action.payload as string;
    });

    // ============ fetchAchievements ============
    builder.addCase(fetchAchievements.pending, (state) => {
      state.loading = true;
      state.error = null;
    });
    builder.addCase(fetchAchievements.fulfilled, (state, action) => {
      state.loading = false;
      state.achievements = action.payload.achievements;
    });
    builder.addCase(fetchAchievements.rejected, (state, action) => {
      state.loading = false;
      state.error = action.payload as string;
    });

    // ============ fetchProgressHistory ============
    builder.addCase(fetchProgressHistory.pending, (state) => {
      state.loading = true;
      state.error = null;
    });
    builder.addCase(fetchProgressHistory.fulfilled, (state, action) => {
      state.loading = false;
      state.history = action.payload.history;
    });
    builder.addCase(fetchProgressHistory.rejected, (state, action) => {
      state.loading = false;
      state.error = action.payload as string;
    });

    // ============ fetchStatistics ============
    builder.addCase(fetchStatistics.pending, (state) => {
      state.loading = true;
      state.error = null;
    });
    builder.addCase(fetchStatistics.fulfilled, (state, action) => {
      state.loading = false;
      state.statistics = action.payload;
    });
    builder.addCase(fetchStatistics.rejected, (state, action) => {
      state.loading = false;
      state.error = action.payload as string;
    });

    // ============ fetchBadges ============
    builder.addCase(fetchBadges.pending, (state) => {
      state.loading = true;
      state.error = null;
    });
    builder.addCase(fetchBadges.fulfilled, (state, action) => {
      state.loading = false;
      state.badges = action.payload.badges;
    });
    builder.addCase(fetchBadges.rejected, (state, action) => {
      state.loading = false;
      state.error = action.payload as string;
    });

    // ============ fetchSkillLevels ============
    builder.addCase(fetchSkillLevels.pending, (state) => {
      state.loading = true;
      state.error = null;
    });
    builder.addCase(fetchSkillLevels.fulfilled, (state, action) => {
      state.loading = false;
      state.skillLevels = action.payload.skill_levels;
    });
    builder.addCase(fetchSkillLevels.rejected, (state, action) => {
      state.loading = false;
      state.error = action.payload as string;
    });

    // ============ exportProgressData ============
    builder.addCase(exportProgressData.pending, (state) => {
      state.loading = true;
      state.error = null;
    });
    builder.addCase(exportProgressData.fulfilled, (state) => {
      state.loading = false;
      // Export doesn't update state, just triggers download
    });
    builder.addCase(exportProgressData.rejected, (state, action) => {
      state.loading = false;
      state.error = action.payload as string;
    });
  },
});

export const {
  clearError,
  resetProgressState,
} = progressSlice.actions;

export default progressSlice.reducer;
