/**
 * The API client (04 §112): one axios instance with the Bearer-attaching
 * request interceptor and the single-flight 401 → refresh → replay-once
 * response interceptor.
 *
 * Why single-flight (9.1 D2, T-09.1-01): refresh rotation is live WITH family
 * reuse-detection — two refreshes from the same stored token blacklist the
 * whole family and log the user out. A module-level in-flight promise makes
 * concurrent 401s share ONE refresh; the `_replayed` marker makes a second
 * replay impossible (no infinite refresh loops, 04 §112).
 *
 * `VITE_API_BASE_URL` is read here and only here (D3) — default `/api/v1`
 * keeps the SPA same-origin with the API through the dev proxy.
 */
import axios, {
  AxiosError,
  AxiosHeaders,
  type AxiosInstance,
  type AxiosResponse,
  type InternalAxiosRequestConfig,
} from "axios";
import { ApiError } from "@/api/errors";
import { refreshSession, terminateSession } from "@/api/session";
import { getAccessToken, getRefreshToken } from "@/api/tokenStore";

/** Marker fields live on axios's config type via module augmentation. */
declare module "axios" {
  export interface AxiosRequestConfig {
    /** This request has already consumed its one replay (D2's bounded loop). */
    _replayed?: boolean;
    /** Marks the refresh POST so interceptors never re-process it. */
    _refreshCall?: boolean;
  }
}

const API_BASE_URL: string =
  (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "/api/v1";
const REQUEST_TIMEOUT_MS = 10_000;

export const apiClient: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  timeout: REQUEST_TIMEOUT_MS,
});

// --- Request interceptor: attach the Bearer token when one exists -----------
// 401s from unauthenticated endpoints (login, register, password reset) carry
// no Bearer token on the request, which is exactly how they bypass the
// refresh path below.
apiClient.interceptors.request.use((config) => {
  const token = getAccessToken();
  if (token !== null && config._refreshCall !== true) {
    config.headers.set("Authorization", `Bearer ${token}`);
  }
  return config;
});


function isBearerRequest(config: InternalAxiosRequestConfig | undefined): boolean {
  const headers = config?.headers;
  if (headers === undefined || headers === null) return false;
  const authorization = AxiosHeaders.from(headers).get("Authorization");
  return typeof authorization === "string" && authorization.startsWith("Bearer ");
}

apiClient.interceptors.response.use(
  (response) => response,
  async (error: unknown) => {
    const axiosError = error as AxiosError;
    const config: InternalAxiosRequestConfig | undefined = axiosError?.config;

    // Non-HTTP failures (offline, timeout, DNS) — normalize, never refresh.
    if (axiosError?.response === undefined) {
      return Promise.reject(
        axiosError?.code === "ECONNABORTED"
          ? new ApiError({ code: "TIMEOUT", message: "The request timed out." }, 0)
          : ApiError.network(),
      );
    }

    const { status, data, headers } = axiosError.response;

    // The refresh POST itself failed — reject for the awaiting single-flight
    // queue to handle (never recurse, never normalize twice).
    if (config?._refreshCall === true) {
      return Promise.reject(ApiError.fromResponse(status, data, headers));
    }

    if (status !== 401) {
      return Promise.reject(ApiError.fromResponse(status, data, headers));
    }

    // 401 on a request that never carried a Bearer token (login, register,
    // password reset) — the refresh path cannot help; reject as-is.
    if (!isBearerRequest(config)) {
      return Promise.reject(ApiError.fromResponse(401, data, headers));
    }

    // A Bearer-carrying request 401'd with no refresh token in the store:
    // nothing to refresh with, the session is over.
    if (getRefreshToken() === null) {
      return Promise.reject(terminateSession());
    }

    // This request already had its one replay and STILL 401s — stop here.
    // Never a second replay; never a second refresh for the same request.
    if (config?._replayed === true || config === undefined) {
      return Promise.reject(terminateSession());
    }

    try {
      await refreshSession();
    } catch {
      // Refresh failed (any error): the session is over.
      return Promise.reject(terminateSession());
    }

    // Replay the original request exactly once, through the same instance so
    // the caller receives the real response.
    config._replayed = true;
    return apiClient.request(config);
  },
);

// --- Typed helpers -----------------------------------------------------------

export async function apiGet<T>(url: string, params?: Record<string, unknown>): Promise<T> {
  const response: AxiosResponse<T> = await apiClient.get(url, { params });
  return response.data;
}

export async function apiPost<T>(url: string, body?: unknown): Promise<T> {
  const response: AxiosResponse<T> = await apiClient.post(url, body);
  return response.data;
}

export async function apiPatch<T>(url: string, body?: unknown): Promise<T> {
  const response: AxiosResponse<T> = await apiClient.patch(url, body);
  return response.data;
}

export async function apiDelete<T>(url: string): Promise<T> {
  const response: AxiosResponse<T> = await apiClient.delete(url);
  return response.data;
}
