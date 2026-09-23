/**
 * The typed auth module: every call against `/auth/*` and `/me/`, with field
 * names byte-exact to the backend serializers (no camelCase translation —
 * the API is the contract, 04 §113).
 */
import { apiClient, apiGet, apiPost } from "@/api/client";
import type {
  LoginResponse,
  TokenRefreshResponse,
  UserPrivate,
} from "@/types/user";

export function login(email: string, password: string): Promise<LoginResponse> {
  return apiPost<LoginResponse>("/auth/login/", { email, password });
}

/** Rotation with family reuse-detection: the response carries BOTH tokens. */
export function refresh(refreshToken: string): Promise<TokenRefreshResponse> {
  return apiPost<TokenRefreshResponse>("/auth/token/refresh/", {
    refresh: refreshToken,
  });
}

/** Blacklist the submitted refresh token; the API answers 204 (04 §16). */
export function logout(refreshToken: string): Promise<void> {
  return apiPost<void>("/auth/logout/", { refresh: refreshToken });
}

export interface RegisterPayload {
  email: string;
  password: string;
  password_confirm: string;
}

export function register(payload: RegisterPayload): Promise<UserPrivate> {
  return apiPost<UserPrivate>("/auth/register/", payload);
}

export function resendVerification(email: string): Promise<void> {
  return apiPost<void>("/auth/verification/resend/", { email });
}

export function verifyEmail(token: string): Promise<void> {
  return apiPost<void>("/auth/verification/verify/", { token });
}

export function requestPasswordReset(email: string): Promise<void> {
  return apiPost<void>("/auth/password-reset/request/", { email });
}

export interface ConfirmPasswordResetPayload {
  token: string;
  new_password: string;
  new_password_confirm: string;
}

export function confirmPasswordReset(
  payload: ConfirmPasswordResetPayload,
): Promise<void> {
  return apiPost<void>("/auth/password-reset/confirm/", payload);
}

export function getMe(): Promise<UserPrivate> {
  return apiGet<UserPrivate>("/me/");
}

/**
 * Session-expired subscribers can also be cleaned up here; re-exported so
 * AuthContext never imports the axios instance directly.
 */
export { apiClient };
