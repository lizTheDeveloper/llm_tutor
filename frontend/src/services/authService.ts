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

interface AuthResponse {
  user: {
    id: string;
    email: string;
    name: string;
    role?: string;
    email_verified?: boolean;
  };
  access_token: string;
  refresh_token: string;
  token_type?: string;
  expires_in?: number;
}

interface OAuthExchangeRequest {
  code: string;
  provider: 'github' | 'google';
}

export const authService = {
  async login(credentials: LoginCredentials): Promise<AuthResponse> {
    const response = await apiClient.post<ApiResponse<AuthResponse>>(
      '/auth/login',
      credentials
    );
    return response.data.data;
  },

  async register(data: RegisterData): Promise<AuthResponse> {
    const response = await apiClient.post<ApiResponse<AuthResponse>>(
      '/auth/register',
      data
    );
    return response.data.data;
  },

  async logout(): Promise<void> {
    await apiClient.post('/auth/logout');
    localStorage.removeItem('authToken');
  },

  async getCurrentUser() {
    const response = await apiClient.get<
      ApiResponse<AuthResponse['user']>
    >('/auth/me');
    return response.data.data;
  },

  async verifyEmail(token: string): Promise<{ message: string }> {
    const response = await apiClient.post<ApiResponse<{ message: string }>>(
      '/auth/verify-email',
      { token }
    );
    return response.data.data;
  },

  async resendVerification(email: string): Promise<{ message: string }> {
    const response = await apiClient.post<ApiResponse<{ message: string }>>(
      '/auth/resend-verification',
      { email }
    );
    return response.data.data;
  },

  async exchangeOAuthCode(
    code: string,
    provider: 'github' | 'google'
  ): Promise<AuthResponse> {
    const response = await apiClient.post<ApiResponse<AuthResponse>>(
      '/auth/oauth/exchange',
      { code, provider }
    );
    return response.data.data;
  },

  initiateGitHubOAuth(): void {
    const apiUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:5000/api/v1';
    window.location.href = `${apiUrl}/auth/oauth/github`;
  },

  initiateGoogleOAuth(): void {
    const apiUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:5000/api/v1';
    window.location.href = `${apiUrl}/auth/oauth/google`;
  },

  saveTokens(tokens: Pick<AuthResponse, 'access_token' | 'refresh_token'>): void {
    localStorage.setItem('authToken', tokens.access_token);
    localStorage.setItem('refreshToken', tokens.refresh_token);
  },

  getAccessToken(): string | null {
    return localStorage.getItem('authToken');
  },

  getRefreshToken(): string | null {
    return localStorage.getItem('refreshToken');
  },

  clearTokens(): void {
    localStorage.removeItem('authToken');
    localStorage.removeItem('refreshToken');
  },
};
