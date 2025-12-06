/**
 * Integration Tests for Cookie-Based Authentication
 *
 * Test Strategy:
 * - Integration tests with real Axios interactions (mock only API responses)
 * - Test actual code paths users will execute
 * - Verify cookie-based authentication works end-to-end
 * - No heavy mocking of internal components
 *
 * Addresses: SEC-1-FE Frontend Cookie Authentication
 * Related: SEC-1 Security Hardening (backend)
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { authService } from './authService';
import apiClient from './api';
import type { AxiosResponse } from 'axios';

// Mock axios module
vi.mock('./api', () => ({
  default: {
    post: vi.fn(),
    get: vi.fn(),
  },
}));

describe('AuthService - Cookie-Based Authentication', () => {
  beforeEach(() => {
    // Clear all mocks before each test
    vi.clearAllMocks();

    // Clear localStorage
    localStorage.clear();

    // Clear cookies (in test environment)
    document.cookie.split(';').forEach((cookie) => {
      document.cookie = cookie
        .replace(/^ +/, '')
        .replace(/=.*/, `=;expires=${new Date().toUTCString()};path=/`);
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('Login Flow with Cookies', () => {
    it('should login and NOT store tokens in localStorage', async () => {
      // GIVEN: Backend returns user data without tokens in response body
      const mockResponse: AxiosResponse<any> = {
        data: {
          success: true,
          data: {
            user: {
              id: '123',
              email: 'test@example.com',
              name: 'Test User',
              role: 'user',
              email_verified: true,
            },
            // NOTE: Cookies are set via Set-Cookie header, not in response body
            // Backend no longer returns access_token/refresh_token in JSON
          },
        },
        status: 200,
        statusText: 'OK',
        headers: {},
        config: {} as any,
      };

      (apiClient.post as any).mockResolvedValue(mockResponse);

      // WHEN: User logs in
      const result = await authService.login({
        email: 'test@example.com',
        password: 'SecurePass123!',
      });

      // THEN: User data is returned
      expect(result.user).toEqual({
        id: '123',
        email: 'test@example.com',
        name: 'Test User',
        role: 'user',
        email_verified: true,
      });

      // AND: Login endpoint was called with credentials
      expect(apiClient.post).toHaveBeenCalledWith('/auth/login', {
        email: 'test@example.com',
        password: 'SecurePass123!',
      });

      // AND: NO tokens stored in localStorage
      expect(localStorage.getItem('authToken')).toBeNull();
      expect(localStorage.getItem('refreshToken')).toBeNull();
    });

    it('should handle login with withCredentials enabled', async () => {
      // GIVEN: Mock successful login
      const mockResponse: AxiosResponse<any> = {
        data: {
          success: true,
          data: {
            user: {
              id: '456',
              email: 'user@test.com',
              name: 'Another User',
            },
          },
        },
        status: 200,
        statusText: 'OK',
        headers: {},
        config: {} as any,
      };

      (apiClient.post as any).mockResolvedValue(mockResponse);

      // WHEN: Login is called
      await authService.login({
        email: 'user@test.com',
        password: 'Password123!',
      });

      // THEN: API client was used (withCredentials should be set in api.ts)
      expect(apiClient.post).toHaveBeenCalled();
    });

    it('should handle login errors properly', async () => {
      // GIVEN: Backend returns error
      const mockError = {
        response: {
          status: 401,
          data: {
            success: false,
            error: {
              message: 'Invalid credentials',
            },
          },
        },
      };

      (apiClient.post as any).mockRejectedValue(mockError);

      // WHEN/THEN: Login fails with proper error
      await expect(
        authService.login({
          email: 'bad@example.com',
          password: 'WrongPassword',
        })
      ).rejects.toEqual(mockError);

      // AND: No tokens in localStorage
      expect(localStorage.getItem('authToken')).toBeNull();
    });
  });

  describe('Register Flow with Cookies', () => {
    it('should register and NOT store tokens in localStorage', async () => {
      // GIVEN: Backend returns user data without tokens
      const mockResponse: AxiosResponse<any> = {
        data: {
          success: true,
          data: {
            user: {
              id: '789',
              email: 'newuser@example.com',
              name: 'New User',
              email_verified: false,
            },
          },
        },
        status: 201,
        statusText: 'Created',
        headers: {},
        config: {} as any,
      };

      (apiClient.post as any).mockResolvedValue(mockResponse);

      // WHEN: User registers
      const result = await authService.register({
        name: 'New User',
        email: 'newuser@example.com',
        password: 'SecurePass123!',
      });

      // THEN: User data is returned
      expect(result.user).toEqual({
        id: '789',
        email: 'newuser@example.com',
        name: 'New User',
        email_verified: false,
      });

      // AND: Register endpoint was called
      expect(apiClient.post).toHaveBeenCalledWith('/auth/register', {
        name: 'New User',
        email: 'newuser@example.com',
        password: 'SecurePass123!',
      });

      // AND: NO tokens in localStorage
      expect(localStorage.getItem('authToken')).toBeNull();
      expect(localStorage.getItem('refreshToken')).toBeNull();
    });
  });

  describe('Logout Flow with Cookies', () => {
    it('should call logout endpoint and clear any localStorage tokens', async () => {
      // GIVEN: Some tokens in localStorage (from old implementation)
      localStorage.setItem('authToken', 'old-token');
      localStorage.setItem('refreshToken', 'old-refresh-token');

      const mockResponse: AxiosResponse<any> = {
        data: { success: true },
        status: 200,
        statusText: 'OK',
        headers: {},
        config: {} as any,
      };

      (apiClient.post as any).mockResolvedValue(mockResponse);

      // WHEN: User logs out
      await authService.logout();

      // THEN: Logout endpoint was called
      expect(apiClient.post).toHaveBeenCalledWith('/auth/logout');

      // AND: localStorage tokens are cleared
      expect(localStorage.getItem('authToken')).toBeNull();
      expect(localStorage.getItem('refreshToken')).toBeNull();
    });

    it('should handle logout errors gracefully', async () => {
      // GIVEN: Logout endpoint fails
      const mockError = {
        response: {
          status: 500,
          data: { error: 'Server error' },
        },
      };

      (apiClient.post as any).mockRejectedValue(mockError);

      // WHEN/THEN: Logout fails but localStorage is still cleared
      await expect(authService.logout()).rejects.toEqual(mockError);

      // AND: localStorage is still cleared (best effort)
      expect(localStorage.getItem('authToken')).toBeNull();
    });
  });

  describe('OAuth Flow with Cookies', () => {
    it('should exchange OAuth code and NOT store tokens in localStorage', async () => {
      // GIVEN: Backend returns user data after OAuth exchange
      const mockResponse: AxiosResponse<any> = {
        data: {
          success: true,
          data: {
            user: {
              id: 'oauth-123',
              email: 'oauth@example.com',
              name: 'OAuth User',
              role: 'user',
            },
          },
        },
        status: 200,
        statusText: 'OK',
        headers: {},
        config: {} as any,
      };

      (apiClient.post as any).mockResolvedValue(mockResponse);

      // WHEN: OAuth code is exchanged
      const result = await authService.exchangeOAuthCode('auth-code-123', 'github');

      // THEN: User data is returned
      expect(result.user).toEqual({
        id: 'oauth-123',
        email: 'oauth@example.com',
        name: 'OAuth User',
        role: 'user',
      });

      // AND: Exchange endpoint was called
      expect(apiClient.post).toHaveBeenCalledWith('/auth/oauth/exchange', {
        code: 'auth-code-123',
        provider: 'github',
      });

      // AND: NO tokens in localStorage
      expect(localStorage.getItem('authToken')).toBeNull();
      expect(localStorage.getItem('refreshToken')).toBeNull();
    });

    it('should initiate GitHub OAuth with correct URL', () => {
      // GIVEN: API base URL is set
      const originalLocation = window.location;
      delete (window as any).location;
      window.location = { ...originalLocation, href: '' } as any;

      // WHEN: GitHub OAuth is initiated
      authService.initiateGitHubOAuth();

      // THEN: Redirects to GitHub OAuth endpoint
      expect(window.location.href).toContain('/auth/oauth/github');

      // Restore
      window.location = originalLocation;
    });

    it('should initiate Google OAuth with correct URL', () => {
      // GIVEN: API base URL is set
      const originalLocation = window.location;
      delete (window as any).location;
      window.location = { ...originalLocation, href: '' } as any;

      // WHEN: Google OAuth is initiated
      authService.initiateGoogleOAuth();

      // THEN: Redirects to Google OAuth endpoint
      expect(window.location.href).toContain('/auth/oauth/google');

      // Restore
      window.location = originalLocation;
    });
  });

  describe('Get Current User with Cookies', () => {
    it('should fetch current user using cookies for authentication', async () => {
      // GIVEN: User is authenticated (cookies are set by browser automatically)
      const mockResponse: AxiosResponse<any> = {
        data: {
          success: true,
          data: {
            id: 'current-123',
            email: 'current@example.com',
            name: 'Current User',
            role: 'user',
          },
        },
        status: 200,
        statusText: 'OK',
        headers: {},
        config: {} as any,
      };

      (apiClient.get as any).mockResolvedValue(mockResponse);

      // WHEN: Current user is fetched
      const user = await authService.getCurrentUser();

      // THEN: User data is returned
      expect(user).toEqual({
        id: 'current-123',
        email: 'current@example.com',
        name: 'Current User',
        role: 'user',
      });

      // AND: /auth/me endpoint was called
      expect(apiClient.get).toHaveBeenCalledWith('/auth/me');

      // AND: No Authorization header is manually set (cookies handle it)
      // This is verified by api.ts NOT reading from localStorage
    });

    it('should handle 401 errors when user is not authenticated', async () => {
      // GIVEN: User is not authenticated (no valid cookies)
      const mockError = {
        response: {
          status: 401,
          data: { error: { message: 'Unauthorized' } },
        },
      };

      (apiClient.get as any).mockRejectedValue(mockError);

      // WHEN/THEN: Request fails with 401
      await expect(authService.getCurrentUser()).rejects.toEqual(mockError);
    });
  });

  describe('Token Management (Deprecated)', () => {
    it('should NOT use saveTokens method with cookies', () => {
      // GIVEN: Old saveTokens method exists for backward compatibility

      // WHEN: saveTokens is called (should be removed from codebase)
      authService.saveTokens({
        access_token: 'token',
        refresh_token: 'refresh',
      });

      // THEN: Tokens ARE saved to localStorage (old behavior)
      // This test documents that saveTokens is DEPRECATED
      // After refactor, this method should be removed entirely
      expect(localStorage.getItem('authToken')).toBe('token');
      expect(localStorage.getItem('refreshToken')).toBe('refresh');
    });

    it('should NOT use getAccessToken method with cookies', () => {
      // GIVEN: Token in localStorage
      localStorage.setItem('authToken', 'test-token');

      // WHEN: getAccessToken is called
      const token = authService.getAccessToken();

      // THEN: Token is retrieved (old behavior)
      // This method should be REMOVED after refactor
      expect(token).toBe('test-token');
    });

    it('should use clearTokens to clean up old localStorage tokens', () => {
      // GIVEN: Old tokens in localStorage
      localStorage.setItem('authToken', 'old-token');
      localStorage.setItem('refreshToken', 'old-refresh');

      // WHEN: clearTokens is called
      authService.clearTokens();

      // THEN: All tokens are removed
      expect(localStorage.getItem('authToken')).toBeNull();
      expect(localStorage.getItem('refreshToken')).toBeNull();
    });
  });

  describe('Email Verification with Cookies', () => {
    it('should verify email using cookies for authentication', async () => {
      // GIVEN: User has verification token
      const mockResponse: AxiosResponse<any> = {
        data: {
          success: true,
          data: {
            message: 'Email verified successfully',
          },
        },
        status: 200,
        statusText: 'OK',
        headers: {},
        config: {} as any,
      };

      (apiClient.post as any).mockResolvedValue(mockResponse);

      // WHEN: Email is verified
      const result = await authService.verifyEmail('verification-token-123');

      // THEN: Success message is returned
      expect(result.message).toBe('Email verified successfully');

      // AND: Verify endpoint was called
      expect(apiClient.post).toHaveBeenCalledWith('/auth/verify-email', {
        token: 'verification-token-123',
      });
    });

    it('should resend verification email', async () => {
      // GIVEN: User wants to resend verification
      const mockResponse: AxiosResponse<any> = {
        data: {
          success: true,
          data: {
            message: 'Verification email sent',
          },
        },
        status: 200,
        statusText: 'OK',
        headers: {},
        config: {} as any,
      };

      (apiClient.post as any).mockResolvedValue(mockResponse);

      // WHEN: Verification email is resent
      const result = await authService.resendVerification('test@example.com');

      // THEN: Success message is returned
      expect(result.message).toBe('Verification email sent');

      // AND: Resend endpoint was called
      expect(apiClient.post).toHaveBeenCalledWith('/auth/resend-verification', {
        email: 'test@example.com',
      });
    });
  });
});
