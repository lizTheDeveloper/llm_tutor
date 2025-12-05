import { createSlice, createAsyncThunk, PayloadAction } from '@reduxjs/toolkit';
import apiClient from '../../services/api';

export interface UserProfile {
  id: number;
  email: string;
  name: string;
  avatar_url: string | null;
  bio: string | null;
  programming_language: string | null;
  skill_level: 'beginner' | 'intermediate' | 'advanced' | null;
  career_goals: string | null;
  learning_style: string | null;
  time_commitment: string | null;
  role: string;
  is_active: boolean;
  is_mentor: boolean;
  current_streak: number;
  longest_streak: number;
  exercises_completed: number;
  last_exercise_date: string | null;
  onboarding_completed: boolean;
  created_at: string;
  updated_at: string;
  last_login: string | null;
}

export interface OnboardingStatus {
  onboarding_completed: boolean;
  user_id: number;
  current_data?: {
    programming_language?: string;
    skill_level?: string;
    career_goals?: string;
    learning_style?: string;
    time_commitment?: string;
  };
}

export interface OnboardingData {
  programming_language: string;
  skill_level: 'beginner' | 'intermediate' | 'advanced';
  career_goals: string;
  learning_style: string;
  time_commitment: string;
}

export interface ProfileUpdateData {
  name?: string;
  bio?: string;
  programming_language?: string;
  skill_level?: 'beginner' | 'intermediate' | 'advanced';
  career_goals?: string;
  learning_style?: string;
  time_commitment?: string;
}

interface ProfileState {
  currentProfile: UserProfile | null;
  onboardingStatus: OnboardingStatus | null;
  loading: boolean;
  error: string | null;
}

const initialState: ProfileState = {
  currentProfile: null,
  onboardingStatus: null,
  loading: false,
  error: null,
};

// Async thunks
export const fetchUserProfile = createAsyncThunk(
  'profile/fetchUserProfile',
  async (_, { rejectWithValue }) => {
    try {
      const response = await apiClient.get('/v1/users/me');
      return response.data;
    } catch (error: any) {
      return rejectWithValue(
        error.response?.data?.error || 'Failed to fetch profile'
      );
    }
  }
);

export const fetchOnboardingStatus = createAsyncThunk(
  'profile/fetchOnboardingStatus',
  async (_, { rejectWithValue }) => {
    try {
      const response = await apiClient.get('/v1/users/onboarding/status');
      return response.data;
    } catch (error: any) {
      return rejectWithValue(
        error.response?.data?.error || 'Failed to fetch onboarding status'
      );
    }
  }
);

export const submitOnboarding = createAsyncThunk(
  'profile/submitOnboarding',
  async (data: OnboardingData, { rejectWithValue }) => {
    try {
      const response = await apiClient.post('/v1/users/onboarding', data);
      return response.data;
    } catch (error: any) {
      return rejectWithValue(
        error.response?.data?.error || 'Failed to submit onboarding'
      );
    }
  }
);

export const updateUserProfile = createAsyncThunk(
  'profile/updateUserProfile',
  async (data: ProfileUpdateData, { rejectWithValue }) => {
    try {
      const response = await apiClient.put('/v1/users/me', data);
      return response.data.profile;
    } catch (error: any) {
      return rejectWithValue(
        error.response?.data?.error || 'Failed to update profile'
      );
    }
  }
);

const profileSlice = createSlice({
  name: 'profile',
  initialState,
  reducers: {
    clearProfileError: (state) => {
      state.error = null;
    },
    clearProfile: (state) => {
      state.currentProfile = null;
      state.onboardingStatus = null;
      state.error = null;
    },
  },
  extraReducers: (builder) => {
    // Fetch user profile
    builder.addCase(fetchUserProfile.pending, (state) => {
      state.loading = true;
      state.error = null;
    });
    builder.addCase(
      fetchUserProfile.fulfilled,
      (state, action: PayloadAction<UserProfile>) => {
        state.loading = false;
        state.currentProfile = action.payload;
      }
    );
    builder.addCase(fetchUserProfile.rejected, (state, action) => {
      state.loading = false;
      state.error = action.payload as string;
    });

    // Fetch onboarding status
    builder.addCase(fetchOnboardingStatus.pending, (state) => {
      state.loading = true;
      state.error = null;
    });
    builder.addCase(
      fetchOnboardingStatus.fulfilled,
      (state, action: PayloadAction<OnboardingStatus>) => {
        state.loading = false;
        state.onboardingStatus = action.payload;
      }
    );
    builder.addCase(fetchOnboardingStatus.rejected, (state, action) => {
      state.loading = false;
      state.error = action.payload as string;
    });

    // Submit onboarding
    builder.addCase(submitOnboarding.pending, (state) => {
      state.loading = true;
      state.error = null;
    });
    builder.addCase(submitOnboarding.fulfilled, (state, action) => {
      state.loading = false;
      // Update profile with onboarding data
      if (state.currentProfile) {
        state.currentProfile = {
          ...state.currentProfile,
          ...action.payload,
        };
      }
      if (state.onboardingStatus) {
        state.onboardingStatus.onboarding_completed = true;
      }
    });
    builder.addCase(submitOnboarding.rejected, (state, action) => {
      state.loading = false;
      state.error = action.payload as string;
    });

    // Update user profile
    builder.addCase(updateUserProfile.pending, (state) => {
      state.loading = true;
      state.error = null;
    });
    builder.addCase(
      updateUserProfile.fulfilled,
      (state, action: PayloadAction<UserProfile>) => {
        state.loading = false;
        state.currentProfile = action.payload;
      }
    );
    builder.addCase(updateUserProfile.rejected, (state, action) => {
      state.loading = false;
      state.error = action.payload as string;
    });
  },
});

export const { clearProfileError, clearProfile } = profileSlice.actions;
export default profileSlice.reducer;
