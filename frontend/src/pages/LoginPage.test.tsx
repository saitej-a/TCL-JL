/**
 * Login screen tests: the three error codes map distinctly, an unverified
 * account routes to /verify-email-pending, and `next` is honored.
 */
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it } from "vitest";

import { AuthProvider } from "@/context/AuthContext";
import { LoginPage } from "@/pages/LoginPage";
import { scriptAdapter } from "@/test/axiosTestHelper";

const LOGIN_OK = {
  access: "acc",
  refresh: "ref",
  user: {
    id: "u1",
    email: "c@example.com",
    is_verified: true,
    created_at: "2026-01-01T00:00:00Z",
    profile_completed: true,
  },
};

function renderLogin(next?: string) {
  return render(
    <MemoryRouter initialEntries={next === undefined ? ["/login"] : [`/login?next=${next}`]}>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/dashboard" element={<p>dashboard-here</p>} />
          <Route path="/verify-email-pending" element={<p>verify-pending-here</p>} />
        </Routes>
      </AuthProvider>
    </MemoryRouter>,
  );
}

async function fillAndSubmit(user: ReturnType<typeof userEvent.setup>) {
  await user.type(screen.getByLabelText("Email address"), "c@example.com");
  await user.type(screen.getByLabelText("Password"), "password123");
  await user.click(screen.getByRole("button", { name: "Sign in" }));
}

describe("LoginPage", () => {
  beforeEach(() => {
    // A leftover refresh token makes the NEXT test's AuthProvider boot fire a
    // refresh POST that desyncs the scripted adapter. Start each test clean.
    localStorage.clear();
  });

  it("shows the invalid-credentials strip on 401", async () => {
    const user = userEvent.setup();
    scriptAdapter([
      {
        url: "/auth/login/",
        respond: () => ({
          status: 401,
          data: { error: { code: "INVALID_CREDENTIALS", message: "nope" } },
        }),
      },
    ]);
    renderLogin();
    await fillAndSubmit(user);
    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent("Invalid email or password.");
    });
  });

  it("shows a countdown on RATE_LIMITED (429 + Retry-After)", async () => {
    const user = userEvent.setup();
    scriptAdapter([
      {
        url: "/auth/login/",
        respond: () => ({
          status: 429,
          headers: { "Retry-After": "30" },
          data: { error: { code: "RATE_LIMITED", message: "slow down" } },
        }),
      },
    ]);
    renderLogin();
    await fillAndSubmit(user);
    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent(/Try again in 30 second/);
    });
  });

  it("shows the suspended copy on ACCOUNT_SUSPENDED", async () => {
    const user = userEvent.setup();
    scriptAdapter([
      {
        url: "/auth/login/",
        respond: () => ({
          status: 403,
          data: { error: { code: "ACCOUNT_SUSPENDED", message: "banned" } },
        }),
      },
    ]);
    renderLogin();
    await fillAndSubmit(user);
    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent("suspended");
    });
  });

  it("routes an unverified account to /verify-email-pending", async () => {
    const user = userEvent.setup();
    scriptAdapter([
      {
        url: "/auth/login/",
        respond: () => ({
          status: 200,
          data: { ...LOGIN_OK, user: { ...LOGIN_OK.user, is_verified: false } },
        }),
      },
    ]);
    renderLogin();
    await fillAndSubmit(user);
    await waitFor(() => {
      expect(screen.getByText("verify-pending-here")).toBeInTheDocument();
    });
  });

  it("honors the next param on success", async () => {
    const user = userEvent.setup();
    scriptAdapter([
      { url: "/auth/login/", respond: () => ({ status: 200, data: LOGIN_OK }) },
    ]);
    renderLogin(encodeURIComponent("/dashboard"));
    await fillAndSubmit(user);
    await waitFor(() => {
      expect(screen.getByText("dashboard-here")).toBeInTheDocument();
    });
  });
});
