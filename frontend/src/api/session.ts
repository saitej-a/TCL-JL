/**
 * The single-flight session restore (boot-time + runtime), split out of
 * `client.ts` so AuthContext can drive a silent refresh through the same
 * module-level queue the interceptor uses — one refresh per storm, wherever
 * it is triggered from (D2).
 */
import { SessionExpiredError } from "@/api/errors";
import {
  clearSession,
  getRefreshToken,
  notifySessionExpired,
  setAccessToken,
  setRefreshToken,
} from "@/api/tokenStore";

let refreshInFlight: Promise<string> | null = null;

/**
 * Refresh exactly once per storm: concurrent callers share the same in-flight
 * promise. On success both rotated tokens are persisted BEFORE the promise
 * resolves (the submitted refresh token was blacklisted at rotation).
 */
export function refreshSession(): Promise<string> {
  if (refreshInFlight !== null) {
    return refreshInFlight;
  }

  const refreshToken = getRefreshToken();
  if (refreshToken === null) {
    return Promise.reject(new SessionExpiredError());
  }

  refreshInFlight = (async () => {
    // Dynamic import: client.ts imports this module statically, so the
    // back-reference stays out of module-evaluation order.
    const { apiClient } = await import("@/api/client");
    try {
      const response = await apiClient.post<{ access: string; refresh: string }>(
        "/auth/token/refresh/",
        { refresh: refreshToken },
        // Marked so neither interceptor re-processes it (augmented config field).
        { _refreshCall: true },
      );
      const { access, refresh } = response.data;
      setRefreshToken(refresh);
      setAccessToken(access);
      return access;
    } catch (error) {
      // A failed refresh never leaves the dead token behind — the boot path
      // relies on this (the interceptor's storm path additionally notifies
      // subscribers via terminateSession).
      clearSession();
      throw error;
    } finally {
      refreshInFlight = null;
    }
  })();

  return refreshInFlight;
}

/** Terminal session end: clear everything and signal the subscribers. */
export function terminateSession(): SessionExpiredError {
  clearSession();
  notifySessionExpired();
  return new SessionExpiredError();
}
