import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  clearAccessToken,
  clearRefreshToken,
  clearSession,
  getAccessToken,
  getRefreshToken,
  notifySessionExpired,
  setAccessToken,
  setRefreshToken,
  subscribe,
} from "./tokenStore";

beforeEach(() => {
  localStorage.clear();
  clearSession();
});

describe("tokenStore (D1: 06 §3.3 Option 1)", () => {
  it("keeps the access token in memory only — never in localStorage/sessionStorage", () => {
    setAccessToken("access-123");
    expect(getAccessToken()).toBe("access-123");
    expect(localStorage.getItem("access_token")).toBeNull();
    expect(localStorage.getItem("accessToken")).toBeNull();
    expect(localStorage.getItem("token")).toBeNull();
    expect(sessionStorage.length).toBe(0);
  });

  it("persists the refresh token under the single namespaced key", () => {
    setRefreshToken("refresh-abc");
    expect(getRefreshToken()).toBe("refresh-abc");
    expect(localStorage.getItem("tjt.refresh_token")).toBe("refresh-abc");
  });

  it("clearSession removes both tokens", () => {
    setAccessToken("a");
    setRefreshToken("r");
    clearSession();
    expect(getAccessToken()).toBeNull();
    expect(getRefreshToken()).toBeNull();
  });

  it("clearRefreshToken/clearAccessToken clear independently", () => {
    setAccessToken("a");
    setRefreshToken("r");
    clearAccessToken();
    expect(getAccessToken()).toBeNull();
    expect(getRefreshToken()).toBe("r");
    clearRefreshToken();
    expect(getRefreshToken()).toBeNull();
  });

  it("notifies subscribers exactly once per signal", () => {
    const listener = vi.fn();
    const unsubscribe = subscribe(listener);
    notifySessionExpired();
    expect(listener).toHaveBeenCalledTimes(1);
    unsubscribe();
    notifySessionExpired();
    expect(listener).toHaveBeenCalledTimes(1); // not called after unsubscribe
  });

  it("degrades gracefully when storage throws", () => {
    const spy = vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new DOMException("denied");
    });
    expect(() => setRefreshToken("r")).not.toThrow();
    expect(getRefreshToken()).toBeNull();
    spy.mockRestore();
  });
});
