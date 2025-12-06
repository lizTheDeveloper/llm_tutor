/**
 * Axios API Client with Cookie-Based Authentication
 *
 * Security Updates (SEC-1-FE):
 * - withCredentials: true enables httpOnly cookie authentication
 * - NO localStorage token storage (prevents XSS attacks)
 * - Cookies are sent automatically by browser on every request
 * - Backend sets httpOnly, secure, SameSite=strict cookies
 *
 * Related: SEC-1 Security Hardening (backend httpOnly cookies)
 */

import axios, { AxiosError } from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:5000/api';

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 30000,
  // SECURITY: Enable sending cookies with cross-origin requests
  // This allows httpOnly cookies to be sent automatically
  withCredentials: true,
});

// REMOVED: Request interceptor that added Authorization header from localStorage
// With cookie-based auth, no manual header injection is needed
// Cookies are sent automatically by the browser when withCredentials: true

apiClient.interceptors.response.use(
  (response) => {
    return response;
  },
  (error: AxiosError) => {
    if (error.response?.status === 401) {
      // Clear any old localStorage tokens (defensive cleanup)
      // Cookies are cleared by backend on logout
      localStorage.removeItem('authToken');
      localStorage.removeItem('refreshToken');

      // Redirect to login page
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

export default apiClient;
