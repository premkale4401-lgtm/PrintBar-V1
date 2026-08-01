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

/** Base URL of the FastAPI backend, e.g. http://localhost:8000 */
export const API_URL: string =
  (import.meta.env.VITE_API_URL as string | undefined) ?? 'http://localhost:8000';

/** Base WebSocket URL of the FastAPI backend, e.g. ws://localhost:8000 */
export const WS_URL: string =
  (import.meta.env.VITE_WS_URL as string | undefined) ?? 'ws://localhost:8000';

/** Supabase project URL (for storage signed URLs only — no direct DB access) */
export const SUPABASE_URL: string =
  (import.meta.env.VITE_SUPABASE_URL as string | undefined) ?? '';

/** Supabase anonymous key */
export const SUPABASE_ANON_KEY: string =
  (import.meta.env.VITE_SUPABASE_ANON_KEY as string | undefined) ?? '';
