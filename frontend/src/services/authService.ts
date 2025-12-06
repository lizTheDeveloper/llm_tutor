/**
 * Authentication Service with Cookie-Based Authentication
 *
 * Security Updates (SEC-1-FE):
 * - NO localStorage token storage (prevents XSS attacks)
 * - Tokens managed via httpOnly cookies set by backend
 * - Cookies are sent automatically with withCredentials: true
 * - Backend sets: httpOnly, secure, SameSite=strict cookies
 *
 * Backend Integration (SEC-1):
 * - Login/Register: Backend sets cookies, returns user data only
 * - Logout: Backend clears cookies
 * - All authenticated requests: Cookies sent automatically
 *
 * Related: SEC-1 Security Hardening (backend httpOnly cookies)
 */

import apiClient from './api';
import type { ApiResponse } from '../types/api';

interface LoginCredentials {
  email: string;
  password: string;
}

interface RegisterData {
  email: string;
  password: string;
  name: string;
}

// Updated AuthResponse: Backend no longer returns tokens in response body
// Tokens are set via Set-Cookie headers instead
interface AuthResponse {
  user: {
    id: string;
    email: string;
    name: string;
    role?: string;
    email_verified?: boolean;
  };
  // REMOVED: access_token, refresh_token
  // These are now set as httpOnly cookies by the backend
}

export const authService = {
  /**
   * Login user with email and password
   * Backend sets httpOnly cookies automatically
   */
  async login(credentials: LoginCredentials): Promise<AuthResponse> {
    const response = await apiClient.post<ApiResponse<AuthResponse>>(
      '/auth/login',
      credentials
    );

    // Backend sets cookies via Set-Cookie header
    // No manual token storage needed
    return response.data.data;
  },

  /**
   * Register new user
   * Backend sets httpOnly cookies automatically
   */
  async register(data: RegisterData): Promise<AuthResponse> {
    const response = await apiClient.post<ApiResponse<AuthResponse>>(
      '/auth/register',
      data
    );

    // Backend sets cookies via Set-Cookie header
    // No manual token storage needed
    return response.data.data;
  },

  /**
   * Logout current user
   * Backend clears httpOnly cookies
   */
  async logout(): Promise<void> {
    await apiClient.post('/auth/logout');

    // Defensive cleanup: Remove any old localStorage tokens
    // from previous implementation
    localStorage.removeItem('authToken');
    localStorage.removeItem('refreshToken');
  },

  /**
   * Get current authenticated user
   * Uses cookies for authentication automatically
   */
  async getCurrentUser() {
    const response = await apiClient.get<
      ApiResponse<AuthResponse['user']>
    >('/auth/me');
    return response.data.data;
  },

  /**
   * Verify email with token
   */
  async verifyEmail(token: string): Promise<{ message: string }> {
    const response = await apiClient.post<ApiResponse<{ message: string }>>(
      '/auth/verify-email',
      { token }
    );
    return response.data.data;
  },

  /**
   * Resend verification email
   */
  async resendVerification(email: string): Promise<{ message: string }> {
    const response = await apiClient.post<ApiResponse<{ message: string }>>(
      '/auth/resend-verification',
      { email }
    );
    return response.data.data;
  },

  /**
   * Exchange OAuth authorization code for user session
   * Backend sets httpOnly cookies automatically
   */
  async exchangeOAuthCode(
    code: string,
    provider: 'github' | 'google'
  ): Promise<AuthResponse> {
    const response = await apiClient.post<ApiResponse<AuthResponse>>(
      '/auth/oauth/exchange',
      { code, provider }
    );

    // Backend sets cookies via Set-Cookie header
    // No manual token storage needed
    return response.data.data;
  },

  /**
   * Initiate GitHub OAuth flow
   * Redirects to backend OAuth endpoint
   */
  initiateGitHubOAuth(): void {
    const apiUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:5000/api';
    window.location.href = `${apiUrl}/auth/oauth/github`;
  },

  /**
   * Initiate Google OAuth flow
   * Redirects to backend OAuth endpoint
   */
  initiateGoogleOAuth(): void {
    const apiUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:5000/api';
    window.location.href = `${apiUrl}/auth/oauth/google`;
  },

  // DEPRECATED METHODS - Kept for backward compatibility during migration
  // These should be removed from all calling code

  /**
   * @deprecated Tokens are now managed via httpOnly cookies
   * This method should not be used with cookie-based auth
   */
  saveTokens(tokens: { access_token: string; refresh_token: string }): void {
    console.warn('[authService] saveTokens is deprecated with cookie-based auth');
    // Still set for backward compatibility during migration
    localStorage.setItem('authToken', tokens.access_token);
    localStorage.setItem('refreshToken', tokens.refresh_token);
  },

  /**
   * @deprecated Tokens are now managed via httpOnly cookies
   * Use cookies instead of localStorage
   */
  getAccessToken(): string | null {
    console.warn('[authService] getAccessToken is deprecated with cookie-based auth');
    return localStorage.getItem('authToken');
  },

  /**
   * @deprecated Tokens are now managed via httpOnly cookies
   * Use cookies instead of localStorage
   */
  getRefreshToken(): string | null {
    console.warn('[authService] getRefreshToken is deprecated with cookie-based auth');
    return localStorage.getItem('refreshToken');
  },

  /**
   * Clear any old localStorage tokens
   * Used for defensive cleanup during logout/errors
   */
  clearTokens(): void {
    localStorage.removeItem('authToken');
    localStorage.removeItem('refreshToken');
  },
};
