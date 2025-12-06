/**
 * Axios API Client with Cookie-Based Authentication + CSRF Protection
 *
 * Security Updates:
 * - (SEC-1-FE) withCredentials: true enables httpOnly cookie authentication
 * - (SEC-1-FE) NO localStorage token storage (prevents XSS attacks)
 * - (SEC-1-FE) Cookies are sent automatically by browser on every request
 * - (SEC-1-FE) Backend sets httpOnly, secure, SameSite=strict cookies
 * - (SEC-3-CSRF) CSRF token automatically included in X-CSRF-Token header
 * - (SEC-3-CSRF) CSRF token read from csrf_token cookie (non-httpOnly)
 *
 * CSRF Protection (Double-Submit Cookie Pattern):
 * 1. Backend sets CSRF token in non-httpOnly cookie on login
 * 2. JavaScript reads token from cookie
 * 3. Token is included in X-CSRF-Token header on state-changing requests
 * 4. Backend verifies cookie token == header token
 *
 * Related: SEC-1 Security Hardening (backend httpOnly cookies)
 * Related: SEC-3-CSRF CSRF Protection (backend middleware)
 */

import axios, { AxiosError } from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:5000/api';

/**
 * Get CSRF token from cookie.
 *
 * The backend sets a non-httpOnly csrf_token cookie that JavaScript can read.
 * This is safe because attackers cannot read cookies due to Same-Origin Policy.
 *
 * @returns CSRF token string or null if not found
 */
function getCsrfToken(): string | null {
  const name = 'csrf_token=';
  const decodedCookie = decodeURIComponent(document.cookie);
  const cookieArray = decodedCookie.split(';');

  for (let i = 0; i < cookieArray.length; i++) {
    let cookie = cookieArray[i];
    while (cookie.charAt(0) === ' ') {
      cookie = cookie.substring(1);
    }
    if (cookie.indexOf(name) === 0) {
      return cookie.substring(name.length, cookie.length);
    }
  }
  return null;
}

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

// SEC-3-CSRF: Add CSRF token to state-changing requests
// This request interceptor adds the X-CSRF-Token header from the csrf_token cookie
apiClient.interceptors.request.use(
  (config) => {
    // Only add CSRF token to state-changing methods
    const csrfProtectedMethods = ['POST', 'PUT', 'PATCH', 'DELETE'];

    if (config.method && csrfProtectedMethods.includes(config.method.toUpperCase())) {
      const csrfToken = getCsrfToken();

      if (csrfToken) {
        config.headers['X-CSRF-Token'] = csrfToken;
      } else {
        console.warn('CSRF token not found in cookies. Request may fail.');
      }
    }

    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

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
