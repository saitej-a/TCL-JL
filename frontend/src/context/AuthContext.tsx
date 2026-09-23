/**
 * Session state (Task 3, D1/D9): one provider over the token store and the
 * typed auth module.
 *
 * - `booting`: the initial silent refresh is in flight — guards render a
 *   skeleton, never a redirect (a reload must not bounce a signed-in user).
 * - The interceptor cannot import React, so session expiry reaches this
 *   context through tokenStore's `subscribe` signal.
 */
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import { getMe, login as authLogin, logout as authLogout } from "@/api/auth";
import { refreshSession } from "@/api/session";
import {
  clearSession,
  getRefreshToken,
  setAccessToken,
  setRefreshToken,
  subscribe,
} from "@/api/tokenStore";
import type { UserPrivate } from "@/types/user";

export type AuthStatus = "booting" | "anonymous" | "authenticated";

interface AuthContextValue {
  status: AuthStatus;
  user: UserPrivate | null;
  isAuthenticated: boolean;
  isBooting: boolean;
  login: (email: string, password: string) => Promise<UserPrivate>;
  logout: () => Promise<void>;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

interface AuthProviderProps {
  children: ReactNode;
}

export function AuthProvider({ children }: AuthProviderProps) {
  const [status, setStatus] = useState<AuthStatus>("booting");
  const [user, setUser] = useState<UserPrivate | null>(null);

  // Boot: restore the session from the stored refresh token, if any.
  useEffect(() => {
    let cancelled = false;

    const storedRefresh = getRefreshToken();
    if (storedRefresh === null) {
      // A visitor: resolve immediately, never a network call.
      setStatus("anonymous");
      return;
    }

    (async () => {
      try {
        await refreshSession();
        const me = await getMe();
        if (cancelled) return;
        setUser(me);
        setStatus("authenticated");
      } catch {
        // refreshSession already cleared the session on failure.
        if (cancelled) return;
        setUser(null);
        setStatus("anonymous");
      }
    })();

    return () => {
      cancelled = true;
    };
  }, []);

  // The interceptor's session-expired signal flips us to anonymous.
  useEffect(() => {
    return subscribe(() => {
      setUser(null);
      setStatus("anonymous");
    });
  }, []);

  const login = useCallback(
    async (email: string, password: string): Promise<UserPrivate> => {
      const response = await authLogin(email, password);
      // Persist BEFORE any state change so a re-render cannot race the store.
      setAccessToken(response.access);
      setRefreshToken(response.refresh);
      setUser(response.user);
      setStatus("authenticated");
      return response.user;
    },
    [],
  );

  const logout = useCallback(async (): Promise<void> => {
    try {
      const refreshToken = getRefreshToken();
      if (refreshToken !== null) {
        await authLogout(refreshToken); // 204; blacklists server-side
      }
    } catch {
      // Best-effort: the endpoint may already be unreachable or the token
      // dead. Storage is cleared unconditionally in `finally` either way.
    } finally {
      clearSession();
      setUser(null);
      setStatus("anonymous");
    }
  }, []);

  const refreshUser = useCallback(async (): Promise<void> => {
    const me = await getMe();
    setUser(me);
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      status,
      user,
      isAuthenticated: status === "authenticated",
      isBooting: status === "booting",
      login,
      logout,
      refreshUser,
    }),
    [status, user, login, logout, refreshUser],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (context === null) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
