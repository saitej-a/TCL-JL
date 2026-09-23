/**
 * The single home of token persistence (9.1 D1, 06 §3.3 Option 1):
 * - the access token lives in memory ONLY (never localStorage, never a cookie);
 * - the refresh token lives in localStorage under one namespaced key.
 *
 * Nothing else in `src/` touches storage for session state. The `subscribe`
 * signal lets the axios client notify AuthContext of session expiry without
 * importing React. Every storage access is guarded — a browser with storage
 * disabled degrades to memory-only instead of crashing.
 */

const REFRESH_STORAGE_KEY = "tjt.refresh_token";

// --- The in-memory access token (never persisted) ---------------------------

let accessToken: string | null = null;

export function getAccessToken(): string | null {
  return accessToken;
}

export function setAccessToken(token: string): void {
  accessToken = token;
}

export function clearAccessToken(): void {
  accessToken = null;
}

// --- The refresh token (localStorage, one namespaced key) -------------------

export function getRefreshToken(): string | null {
  try {
    return localStorage.getItem(REFRESH_STORAGE_KEY);
  } catch {
    return null;
  }
}

export function setRefreshToken(token: string): void {
  try {
    localStorage.setItem(REFRESH_STORAGE_KEY, token);
  } catch {
    // Storage disabled: the refresh token stays out of memory entirely —
    // silent refresh is lost for this session, which is the safe direction.
  }
}

export function clearRefreshToken(): void {
  try {
    localStorage.removeItem(REFRESH_STORAGE_KEY);
  } catch {
    // Nothing to clean up if storage is unavailable.
  }
}

/** Clear both halves of the session (logout, refresh failure, replay-loop stop). */
export function clearSession(): void {
  clearAccessToken();
  clearRefreshToken();
}

// --- The session-expired signal ---------------------------------------------

type SessionExpiredListener = () => void;

const listeners = new Set<SessionExpiredListener>();

/** AuthContext subscribes at mount; the client notifies on terminal 401s. */
export function subscribe(listener: SessionExpiredListener): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

export function notifySessionExpired(): void {
  listeners.forEach((listener) => listener());
}
