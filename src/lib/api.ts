/**
 * PrintBar — Axios HTTP Client
 *
 * - Injects guest session Bearer token on every request.
 * - Extracts structured backend error codes.
 * - Logs requests in development.
 *
 * Never import axios directly in components or hooks.
 * Always import `apiClient` from this module.
 */

import axios, {
  AxiosError,
  AxiosRequestConfig,
  AxiosResponse,
  InternalAxiosRequestConfig,
} from 'axios';
import { API_URL } from './env';

// ─── Token Storage Keys ───────────────────────────────────────────────────────

/** Guest session JWT — stored in sessionStorage (clears on tab close) */
export const GUEST_TOKEN_KEY = 'pb_guest_token';

/** Admin JWT access token — stored in localStorage */
export const ADMIN_TOKEN_KEY = 'pb_admin_token';

/** Admin refresh token — stored in localStorage */
export const ADMIN_REFRESH_KEY = 'pb_admin_refresh';

// ─── Token Helpers ────────────────────────────────────────────────────────────

export function getGuestToken(): string | null {
  return sessionStorage.getItem(GUEST_TOKEN_KEY);
}

export function setGuestToken(token: string): void {
  sessionStorage.setItem(GUEST_TOKEN_KEY, token);
}

export function clearGuestToken(): void {
  sessionStorage.removeItem(GUEST_TOKEN_KEY);
}

export function getAdminToken(): string | null {
  return localStorage.getItem(ADMIN_TOKEN_KEY);
}

export function setAdminTokens(accessToken: string, refreshToken: string): void {
  localStorage.setItem(ADMIN_TOKEN_KEY, accessToken);
  localStorage.setItem(ADMIN_REFRESH_KEY, refreshToken);
}

export function clearAdminTokens(): void {
  localStorage.removeItem(ADMIN_TOKEN_KEY);
  localStorage.removeItem(ADMIN_REFRESH_KEY);
}

// ─── Structured API Error ─────────────────────────────────────────────────────

export interface ApiErrorPayload {
  code: string;
  message: string;
}

export class PrintBarApiError extends Error {
  public readonly code: string;
  public readonly statusCode: number;

  constructor(code: string, message: string, statusCode: number) {
    super(message);
    this.name = 'PrintBarApiError';
    this.code = code;
    this.statusCode = statusCode;
  }
}

// ─── Axios Instance ───────────────────────────────────────────────────────────

export const apiClient = axios.create({
  baseURL: `${API_URL}/api/v1`,
  timeout: 30_000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor — inject appropriate Bearer token.
apiClient.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    // Admin token takes priority over guest token.
    const adminToken = getAdminToken();
    const guestToken = getGuestToken();
    const token = adminToken ?? guestToken;

    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }

    return config;
  },
  (error) => Promise.reject(error),
);

// Response interceptor — normalize backend error shape.
apiClient.interceptors.response.use(
  (response: AxiosResponse) => response,
  (error: AxiosError<{ success: false; error: ApiErrorPayload }>) => {
    const statusCode = error.response?.status ?? 0;
    const errorPayload = error.response?.data?.error;

    if (errorPayload) {
      return Promise.reject(
        new PrintBarApiError(errorPayload.code, errorPayload.message, statusCode),
      );
    }

    // Network / timeout errors.
    if (error.code === 'ECONNABORTED') {
      return Promise.reject(
        new PrintBarApiError('SYS_TIMEOUT', 'Request timed out. Please try again.', statusCode),
      );
    }

    if (!error.response) {
      return Promise.reject(
        new PrintBarApiError(
          'SYS_NETWORK',
          'Network error. Check your connection and try again.',
          0,
        ),
      );
    }

    let friendlyMessage = error.message;
    if (statusCode === 429) {
      friendlyMessage = 'Too many requests. Please wait a moment and try again.';
    } else if (statusCode === 502 || statusCode === 503 || statusCode === 504) {
      friendlyMessage = 'Our servers are currently unavailable. Please try again in a few minutes.';
    } else if (statusCode >= 500) {
      friendlyMessage = 'An unexpected server error occurred. Please try again later.';
    }

    return Promise.reject(
      new PrintBarApiError('SYS_UNKNOWN', friendlyMessage, statusCode),
    );
  },
);

// ─── Typed request helper ─────────────────────────────────────────────────────

/** Makes a request and returns `response.data.data` (unwraps the backend envelope). */
export async function apiFetch<T>(config: AxiosRequestConfig): Promise<T> {
  const response = await apiClient.request<{ success: true; data: T }>(config);
  return response.data.data;
}
