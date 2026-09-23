/**
 * The phase's core evidence (Task 2, D2): the interceptor contract, driven by
 * swapping the axios instance's adapter — no mocking dependency (D8).
 *
 * The adapter receives each request in order and answers from a scripted
 * queue, so the tests observe real interceptor behavior: attach, refresh,
 * replay, and the single-flight queue.
 */
import type { AxiosAdapter, AxiosRequestConfig } from "axios";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { SessionExpiredError } from "./errors";
import { apiClient } from "./client";
import {
  clearSession,
  getAccessToken,
  getRefreshToken,
  setAccessToken,
  setRefreshToken,
  subscribe,
} from "./tokenStore";

interface ScriptedCall {
  /** Match the URL suffix (after the baseURL), e.g. "/auth/token/refresh/". */
  url: string;
  /** The method, lowercased. */
  method?: string;
  respond: (config: AxiosRequestConfig) => {
    status: number;
    data?: unknown;
    headers?: Record<string, string>;
  };
}

function scriptAdapter(script: ScriptedCall[]): { calls: AxiosRequestConfig[] } {
  const calls: AxiosRequestConfig[] = [];
  let cursor = 0;
  const adapter: AxiosAdapter = (config) => {
    calls.push(config);
    const step = script[cursor];
    cursor += 1;
    if (step === undefined) {
      return Promise.reject(new Error(`unexpected request #${cursor}: ${String(config.url)}`));
    }
    if (step.method !== undefined && config.method?.toLowerCase() !== step.method) {
      return Promise.reject(
        new Error(`expected ${step.method}, got ${String(config.method)} for ${String(config.url)}`),
      );
    }
    if (!String(config.url).endsWith(step.url)) {
      return Promise.reject(
        new Error(`expected url to end with ${step.url}, got ${String(config.url)}`),
      );
    }
    const answer = step.respond(config);
    const response = {
      data: answer.data,
      status: answer.status,
      statusText: "",
      headers: answer.headers ?? {},
      config,
      request: {},
    };
    if (answer.status >= 200 && answer.status < 300) {
      return Promise.resolve(response);
    }
    // Axios rejects non-2xx with an AxiosError-shaped object.
    const error = new Error(`Request failed with status code ${answer.status}`) as Error & {
      config: unknown;
      response: unknown;
      isAxiosError: boolean;
    };
    error.config = config;
    error.response = response;
    error.isAxiosError = true;
    return Promise.reject(error);
  };
  apiClient.defaults.adapter = adapter;
  return { calls };
}

beforeEach(() => {
  localStorage.clear();
  clearSession();
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("request interceptor: Bearer attachment", () => {
  it("attaches the Bearer token when an access token exists", async () => {
    setAccessToken("access-1");
    const { calls } = scriptAdapter([
      { url: "/me/", respond: () => ({ status: 200, data: {} }) },
    ]);
    await apiClient.get("/me/");
    expect(calls[0]?.headers?.Authorization).toBe("Bearer access-1");
  });

  it("attaches nothing when no access token exists (auth-endpoint 401s bypass refresh)", async () => {
    const { calls } = scriptAdapter([
      { url: "/auth/login/", method: "post", respond: () => ({ status: 401, data: {} }) },
    ]);
    await expect(apiClient.post("/auth/login/", {})).rejects.toMatchObject({ status: 401 });
    expect(calls[0]?.headers?.Authorization).toBeUndefined();
  });
});

describe("single 401: one refresh, one replay", () => {
  it("refreshes once, persists the rotated refresh token, and replays with the new Bearer", async () => {
    // The access token exists but is expired server-side; the refresh token
    // is in the store. (A request with NO Bearer at all must not refresh —
    // that branch is covered below; boot-time restore is AuthContext's job.)
    setAccessToken("expired-access");
    setRefreshToken("stale-refresh");
    const { calls } = scriptAdapter([
      // 1. the original request 401s
      {
        url: "/me/",
        respond: () => ({ status: 401, data: { error: { code: "AUTH", message: "expired" } } }),
      },
      // 2. the refresh POST answers with BOTH rotated tokens
      {
        url: "/auth/token/refresh/",
        method: "post",
        respond: () => ({ status: 200, data: { access: "new-access", refresh: "rotated-refresh" } }),
      },
      // 3. the replay succeeds
      { url: "/me/", respond: () => ({ status: 200, data: { id: "u1", email: "e@x.io" } }) },
    ]);

    const result = await apiClient.get<{ id: string; email: string }>("/me/");
    expect(result.data).toEqual({ id: "u1", email: "e@x.io" }); // the caller sees the REPLAYED response

    const refreshCall = calls.find((c) => String(c.url).endsWith("/auth/token/refresh/"));
    expect(refreshCall).toBeDefined();
    expect(refreshCall?.data).toEqual(JSON.stringify({ refresh: "stale-refresh" }));
    // The rotated refresh token was persisted BEFORE the replay fired:
    // the replay (3rd call) happens after the store already holds it.
    expect(getRefreshToken()).toBe("rotated-refresh");
    expect(getAccessToken()).toBe("new-access");
    const replayCall = calls[2] as (typeof calls)[number] & { _replayed?: boolean };
    expect(replayCall?.headers?.Authorization).toBe("Bearer new-access");
    expect(replayCall?._replayed).toBe(true);
    expect(calls).toHaveLength(3);
  });

  it("sends the refresh POST without a Bearer header", async () => {
    setAccessToken("expired-access");
    setRefreshToken("stale-refresh");
    const { calls } = scriptAdapter([
      { url: "/me/", respond: () => ({ status: 401, data: {} }) },
      {
        url: "/auth/token/refresh/",
        method: "post",
        respond: () => ({ status: 200, data: { access: "a2", refresh: "r2" } }),
      },
      { url: "/me/", respond: () => ({ status: 200, data: {} }) },
    ]);
    await apiClient.get("/me/");
    const refreshCall = calls.find((c) => String(c.url).endsWith("/auth/token/refresh/"));
    expect(refreshCall?.headers?.Authorization).toBeUndefined();
  });
});

describe("concurrent 401s: the D2 proof", () => {
  it("shares exactly ONE refresh POST across concurrent 401s and replays both", async () => {
    setAccessToken("expired-access");
    setRefreshToken("stale-refresh");
    const { calls } = scriptAdapter([
      { url: "/me/", respond: () => ({ status: 401, data: {} }) }, // original 1
      { url: "/me/", respond: () => ({ status: 401, data: {} }) }, // original 2
      {
        url: "/auth/token/refresh/",
        method: "post",
        respond: () => ({ status: 200, data: { access: "shared-access", refresh: "rotated" } }),
      },
      { url: "/me/", respond: () => ({ status: 200, data: { which: 1 } }) }, // replay 1
      { url: "/me/", respond: () => ({ status: 200, data: { which: 2 } }) }, // replay 2
    ]);

    const [first, second] = await Promise.all([
      apiClient.get<{ which: number }>("/me/"),
      apiClient.get<{ which: number }>("/me/"),
    ]);
    expect(first.data).toEqual({ which: 1 });
    expect(second.data).toEqual({ which: 2 });

    const refreshCalls = calls.filter((c) => String(c.url).endsWith("/auth/token/refresh/"));
    expect(refreshCalls).toHaveLength(1); // THE assertion: one refresh, not a family revocation
    expect(calls).toHaveLength(5);
    expect(getRefreshToken()).toBe("rotated");
  });
});

describe("terminal 401s: the bounded loop", () => {
  it("does not refresh a second time when the replay 401s again; clears session and notifies", async () => {
    setAccessToken("expired-access");
    setRefreshToken("stale-refresh");
    const listener = vi.fn();
    const unsubscribe = subscribe(listener);
    try {
      const { calls } = scriptAdapter([
        { url: "/me/", respond: () => ({ status: 401, data: {} }) }, // original
        {
          url: "/auth/token/refresh/",
          method: "post",
          respond: () => ({ status: 200, data: { access: "a2", refresh: "r2" } }),
        },
        { url: "/me/", respond: () => ({ status: 401, data: {} }) }, // the replay still 401s
      ]);

      await expect(apiClient.get("/me/")).rejects.toBeInstanceOf(SessionExpiredError);
      const refreshCalls = calls.filter((c) => String(c.url).endsWith("/auth/token/refresh/"));
      expect(refreshCalls).toHaveLength(1); // no loop
      expect(getAccessToken()).toBeNull();
      expect(getRefreshToken()).toBeNull();
      expect(listener).toHaveBeenCalledTimes(1);
    } finally {
      unsubscribe();
    }
  });

  it("rejects with SessionExpiredError and clears the session when refresh fails", async () => {
    setAccessToken("expired-access");
    setRefreshToken("dead-refresh");
    const listener = vi.fn();
    const unsubscribe = subscribe(listener);
    try {
      scriptAdapter([
        { url: "/me/", respond: () => ({ status: 401, data: {} }) },
        {
          url: "/auth/token/refresh/",
          method: "post",
          respond: () => ({
            status: 401,
            data: { error: { code: "INVALID_CREDENTIALS", message: "Token is invalid or expired." } },
          }),
        },
      ]);

      await expect(apiClient.get("/me/")).rejects.toBeInstanceOf(SessionExpiredError);
      expect(getAccessToken()).toBeNull();
      expect(getRefreshToken()).toBeNull();
      expect(listener).toHaveBeenCalledTimes(1);
    } finally {
      unsubscribe();
    }
  });

  it("rejects with SessionExpiredError without attempting refresh when no refresh token exists", async () => {
    // Access token present but expired (the server 401s it); with no refresh
    // token in the store there is nothing to refresh with — one request, no
    // refresh POST, typed session-expired rejection.
    const { calls } = scriptAdapter([
      { url: "/me/", respond: () => ({ status: 401, data: {} }) },
    ]);
    setAccessToken("expired-access");
    await expect(apiClient.get("/me/")).rejects.toBeInstanceOf(SessionExpiredError);
    expect(calls).toHaveLength(1);
    expect(calls.filter((c) => String(c.url).endsWith("/auth/token/refresh/"))).toHaveLength(0);
  });
});

describe("unauthenticated endpoints never refresh", () => {
  it("a login 401 performs no refresh call", async () => {
    scriptAdapter([
      {
        url: "/auth/login/",
        method: "post",
        respond: () => ({
          status: 401,
          data: { error: { code: "INVALID_CREDENTIALS", message: "Invalid email or password." } },
        }),
      },
    ]);
    await expect(apiClient.post("/auth/login/", { email: "e", password: "p" })).rejects.toMatchObject({
      code: "INVALID_CREDENTIALS",
      status: 401,
    });
    expect(getRefreshToken()).toBeNull();
  });
});

describe("error normalization (04 §10)", () => {
  it("normalizes a 400 envelope with details", async () => {
    scriptAdapter([
      {
        url: "/auth/register/",
        method: "post",
        respond: () => ({
          status: 400,
          data: {
            error: {
              code: "VALIDATION_ERROR",
              message: "The request contains invalid fields.",
              details: { email: ["Enter a valid email address."] },
            },
          },
        }),
      },
    ]);
    await expect(apiClient.post("/auth/register/", {})).rejects.toMatchObject({
      code: "VALIDATION_ERROR",
      status: 400,
      details: { email: ["Enter a valid email address."] },
    });
  });

  it("normalizes 403 ACCOUNT_SUSPENDED and 404 NOT_FOUND", async () => {
    scriptAdapter([
      {
        url: "/auth/login/",
        method: "post",
        respond: () => ({
          status: 403,
          data: { error: { code: "ACCOUNT_SUSPENDED", message: "suspended" } },
        }),
      },
      {
        url: "/widgets/",
        respond: () => ({ status: 404, data: { error: { code: "NOT_FOUND", message: "nope" } } }),
      },
      { url: "/widgets/", respond: () => ({ status: 200, data: {} }) },
    ]);
    await expect(apiClient.post("/auth/login/", {})).rejects.toMatchObject({
      code: "ACCOUNT_SUSPENDED",
      status: 403,
    });
    await expect(apiClient.get("/widgets/")).rejects.toMatchObject({
      code: "NOT_FOUND",
      status: 404,
    });
  });

  it("parses Retry-After from the header on 429", async () => {
    scriptAdapter([
      {
        url: "/auth/login/",
        method: "post",
        respond: () => ({
          status: 429,
          headers: { "Retry-After": "30" },
          data: {
            error: { code: "RATE_LIMITED", message: "Too many requests.", retry_after_seconds: 30 },
          },
        }),
      },
    ]);
    await expect(apiClient.post("/auth/login/", {})).rejects.toMatchObject({
      code: "RATE_LIMITED",
      status: 429,
      retryAfter: 30,
    });
  });

  it("wraps network failures in a NETWORK_ERROR ApiError", async () => {
    const failingAdapter: AxiosAdapter = () =>
      Promise.reject(Object.assign(new Error("Network Error"), { isAxiosError: true }));
    apiClient.defaults.adapter = failingAdapter;
    await expect(apiClient.get("/me/")).rejects.toMatchObject({ code: "NETWORK_ERROR" });
  });
});
