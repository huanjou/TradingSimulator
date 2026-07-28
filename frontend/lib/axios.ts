import axios from 'axios';

const api = axios.create({
  withCredentials: true,
  xsrfCookieName: 'csrf_token',
  xsrfHeaderName: 'X-CSRF-Token',
});

// Auth endpoints must never trigger a token refresh (avoids retry loops).
const AUTH_PATHS = [
  '/api/v1/auth/login',
  '/api/v1/auth/register',
  '/api/v1/auth/refresh',
  '/api/v1/auth/logout',
];

// The auth store is created per-provider instance, so AuthProvider registers
// a callback invoked when a refresh attempt fails (session truly expired).
let onAuthFailure: (() => void) | null = null;

export function setOnAuthFailure(handler: (() => void) | null) {
  onAuthFailure = handler;
}

// Deduplicate concurrent refreshes: parallel 401s share one refresh call.
let refreshPromise: Promise<unknown> | null = null;

function refreshAccessToken() {
  if (!refreshPromise) {
    refreshPromise = api.post('/api/v1/auth/refresh').finally(() => {
      refreshPromise = null;
    });
  }
  return refreshPromise;
}

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;
    const isAuthPath = AUTH_PATHS.some((path) => originalRequest?.url?.includes(path));

    if (
      error.response?.status === 401 &&
      originalRequest &&
      !originalRequest._retry &&
      !isAuthPath
    ) {
      originalRequest._retry = true;
      try {
        await refreshAccessToken();
        return api(originalRequest);
      } catch {
        // Refresh failed: session is over, hand off to the auth store.
        onAuthFailure?.();
        return Promise.reject(error);
      }
    }
    return Promise.reject(error);
  },
);

export default api;
