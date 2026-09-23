/**
 * AuthContext tests (Task 3): driven through the scripted axios adapter —
 * no mocking dependency (D8).
 */
import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it } from "vitest";

import { scriptAdapter } from "@/test/axiosTestHelper";
import {
  getAccessToken,
  getRefreshToken,
  notifySessionExpired,
} from "@/api/tokenStore";

import { AuthProvider, useAuth } from "./AuthContext";

function AuthProbe(): React.ReactElement {
  const { status, user, login, logout, isAuthenticated, isBooting } = useAuth();
  return (
    <div>
      <span data-testid="status">{status}</span>
      <span data-testid="user">{user === null ? "none" : user.email}</span>
      <span data-testid="isAuth">{String(isAuthenticated)}</span>
      <span data-testid="booting">{String(isBooting)}</span>
      <button onClick={() => void login("candidate@example.com", "Str0ngPass!x")}>
        login
      </button>
      <button onClick={() => void logout()}>logout</button>
    </div>
  );
}

async function renderProbe() {
  render(
    <AuthProvider>
      <AuthProbe />
    </AuthProvider>,
  );
  await waitFor(() => {
    expect(screen.getByTestId("booting")).toHaveTextContent("false");
  });
}

beforeEach(() => {
  localStorage.clear();
});

describe("AuthProvider boot", () => {
  it("resolves to anonymous without any adapter call when no refresh token is stored", async () => {
    const { calls } = scriptAdapter([
      { url: "/me/", respond: () => ({ status: 200, data: {} }) },
    ]);
    await renderProbe();
    expect(screen.getByTestId("status")).toHaveTextContent("anonymous");
    expect(calls).toHaveLength(0);
  });

  it("goes booting → authenticated via the silent refresh and /me/", async () => {
    localStorage.setItem("tjt.refresh_token", "stored-refresh");
    scriptAdapter([
      {
        url: "/auth/token/refresh/",
        method: "post",
        respond: () => ({ status: 200, data: { access: "a1", refresh: "r1" } }),
      },
      {
        url: "/me/",
        respond: () => ({
          status: 200,
          data: { id: "u1", email: "candidate@example.com", is_verified: true, created_at: "t", profile_completed: false },
        }),
      },
    ]);
    await renderProbe();
    expect(screen.getByTestId("status")).toHaveTextContent("authenticated");
    expect(screen.getByTestId("user")).toHaveTextContent("candidate@example.com");
    expect(getAccessToken()).toBe("a1");
  });

  it("resolves to anonymous and clears storage when the stored refresh token is invalid", async () => {
    localStorage.setItem("tjt.refresh_token", "dead-refresh");
    scriptAdapter([
      {
        url: "/auth/token/refresh/",
        method: "post",
        respond: () => ({ status: 401, data: {} }),
      },
    ]);
    await renderProbe();
    expect(screen.getByTestId("status")).toHaveTextContent("anonymous");
    expect(getRefreshToken()).toBeNull();
  });
});

describe("login/logout", () => {
  it("login stores both tokens and sets the user", async () => {
    const user = userEvent.setup();
    scriptAdapter([
      {
        url: "/auth/login/",
        method: "post",
        respond: () => ({
          status: 200,
          data: {
            access: "acc",
            refresh: "ref",
            user: { id: "u1", email: "candidate@example.com", is_verified: true, created_at: "t", profile_completed: false },
          },
        }),
      },
    ]);
    await renderProbe();
    await user.click(screen.getByText("login"));
    await waitFor(() => {
      expect(screen.getByTestId("status")).toHaveTextContent("authenticated");
    });
    expect(getAccessToken()).toBe("acc");
    expect(getRefreshToken()).toBe("ref");
    expect(screen.getByTestId("user")).toHaveTextContent("candidate@example.com");
  });

  it("logout calls the endpoint and clears storage even when the call fails", async () => {
    const user = userEvent.setup();
    // Start authenticated: store a refresh token, let boot restore a session.
    localStorage.setItem("tjt.refresh_token", "stored-refresh");
    scriptAdapter([
      {
        url: "/auth/token/refresh/",
        method: "post",
        respond: () => ({ status: 200, data: { access: "a1", refresh: "r1" } }),
      },
      {
        url: "/me/",
        respond: () => ({
          status: 200,
          data: { id: "u1", email: "candidate@example.com", is_verified: true, created_at: "t", profile_completed: false },
        }),
      },
      // The logout call itself fails (network/5xx) — storage must STILL clear.
      { url: "/auth/logout/", method: "post", respond: () => ({ status: 500, data: {} }) },
    ]);
    await renderProbe();
    expect(screen.getByTestId("status")).toHaveTextContent("authenticated");
    await user.click(screen.getByText("logout"));
    await waitFor(() => {
      expect(screen.getByTestId("status")).toHaveTextContent("anonymous");
    });
    expect(getAccessToken()).toBeNull();
    expect(getRefreshToken()).toBeNull();
  });
});

describe("the session-expired signal", () => {
  it("flips an authenticated session to anonymous when the interceptor fires", async () => {
    localStorage.setItem("tjt.refresh_token", "stored-refresh");
    scriptAdapter([
      {
        url: "/auth/token/refresh/",
        method: "post",
        respond: () => ({ status: 200, data: { access: "a1", refresh: "r1" } }),
      },
      {
        url: "/me/",
        respond: () => ({
          status: 200,
          data: { id: "u1", email: "candidate@example.com", is_verified: true, created_at: "t", profile_completed: false },
        }),
      },
    ]);
    await renderProbe();
    expect(screen.getByTestId("status")).toHaveTextContent("authenticated");

    act(() => {
      notifySessionExpired();
    });
    expect(screen.getByTestId("status")).toHaveTextContent("anonymous");
    expect(screen.getByTestId("user")).toHaveTextContent("none");
  });
});
