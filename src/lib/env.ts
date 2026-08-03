/**
 * PrintBar — Type-safe environment variable access.
 *
 * Only VITE_ prefixed variables are exposed to the browser bundle.
 * Never access import.meta.env directly outside this file.
 */

function requireEnv(key: string): string {
  const value = (import.meta.env as Record<string, string>)[key];
  if (!value) {
    throw new Error(`[PrintBar] Missing required environment variable: ${key}`);
  }
  return value;
}

function getDynamicBackendHost(): string {
  if (typeof window !== 'undefined' && window.location && window.location.hostname) {
    return window.location.hostname;
  }
  return 'localhost';
}

function getDynamicProtocol(): string {
  if (typeof window !== 'undefined' && window.location && window.location.protocol) {
    return window.location.protocol;
  }
  return 'http:';
}

function getViteApiUrl(): string | undefined {
  const url = import.meta.env.VITE_API_URL as string | undefined;
  // Ignore hardcoded localhost in .env if the browser is NOT on localhost
  if (url && (url.includes('localhost') || url.includes('127.0.0.1')) && getDynamicBackendHost() !== 'localhost' && getDynamicBackendHost() !== '127.0.0.1') {
    return undefined;
  }
  return url;
}

function getViteWsUrl(): string | undefined {
  const url = import.meta.env.VITE_WS_URL as string | undefined;
  // Ignore hardcoded localhost in .env if the browser is NOT on localhost
  if (url && (url.includes('localhost') || url.includes('127.0.0.1')) && getDynamicBackendHost() !== 'localhost' && getDynamicBackendHost() !== '127.0.0.1') {
    return undefined;
  }
  return url;
}

/** Base URL of the FastAPI backend, e.g. http://localhost:8000 or http://10.107.16.76:8000 */
export const API_URL: string =
  getViteApiUrl() ??
  `${getDynamicProtocol()}//${getDynamicBackendHost()}:8000`;

/** Base WebSocket URL of the FastAPI backend, e.g. ws://localhost:8000 or ws://10.107.16.76:8000 */
export const WS_URL: string =
  getViteWsUrl() ??
  `${getDynamicProtocol() === 'https:' ? 'wss:' : 'ws:'}//${getDynamicBackendHost()}:8000`;

/** Supabase project URL (for storage signed URLs only — no direct DB access) */
export const SUPABASE_URL: string =
  (import.meta.env.VITE_SUPABASE_URL as string | undefined) ?? '';

/** Supabase anonymous key */
export const SUPABASE_ANON_KEY: string =
  (import.meta.env.VITE_SUPABASE_ANON_KEY as string | undefined) ?? '';

/**
 * Razorpay public Key ID.
 *
 * This is the ONLY Razorpay variable in the frontend bundle.
 * VITE_RAZORPAY_KEY_SECRET must NEVER exist — KEY_SECRET is backend-only.
 * The KEY_ID is returned by the backend create-order endpoint, but we also
 * read it here so the checkout hook can open the modal immediately.
 */
export const RAZORPAY_KEY_ID: string =
  (import.meta.env.VITE_RAZORPAY_KEY_ID as string | undefined) ?? '';
