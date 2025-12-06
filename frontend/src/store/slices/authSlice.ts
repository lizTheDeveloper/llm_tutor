/**
 * Redux Auth Slice with Cookie-Based Authentication
 *
 * Security Updates (SEC-1-FE):
 * - NO token storage in Redux state (prevents XSS attacks)
 * - Tokens managed via httpOnly cookies set by backend
 * - Redux only stores user profile data, not sensitive tokens
 *
 * Related: SEC-1 Security Hardening (backend httpOnly cookies)
 */

import { createSlice } from '@reduxjs/toolkit';
import type { PayloadAction } from '@reduxjs/toolkit';

interface User {
  id: string;
  email: string;
  name: string;
  role?: string;
  emailVerified?: boolean;
}

interface AuthState {
  user: User | null;
  // REMOVED: token field (tokens are in httpOnly cookies, not accessible to JS)
  isAuthenticated: boolean;
  loading: boolean;
  error: string | null;
}

const initialState: AuthState = {
  user: null,
  isAuthenticated: false,
  loading: false,
  error: null,
};

const authSlice = createSlice({
  name: 'auth',
  initialState,
  reducers: {
    /**
     * Set user credentials after successful login/register
     * Backend sets cookies automatically, we only store user data
     */
    setCredentials: (
      state,
      action: PayloadAction<{ user: User }>
    ) => {
      state.user = action.payload.user;
      state.isAuthenticated = true;
      state.error = null;
    },
    /**
     * Set user profile data
     */
    setUser: (state, action: PayloadAction<User>) => {
      state.user = action.payload;
      state.isAuthenticated = true;
      state.error = null;
    },
    /**
     * Logout user
     * Backend clears cookies via /auth/logout endpoint
     */
    logout: (state) => {
      state.user = null;
      state.isAuthenticated = false;
      state.error = null;
    },
    /**
     * Set loading state
     */
    setLoading: (state, action: PayloadAction<boolean>) => {
      state.loading = action.payload;
    },
    /**
     * Set error message
     */
    setError: (state, action: PayloadAction<string | null>) => {
      state.error = action.payload;
      state.loading = false;
    },
  },
});

export const { setCredentials, setUser, logout, setLoading, setError } =
  authSlice.actions;

export default authSlice.reducer;
