/**
 * Guard tests (Task 3): RequireAuth/PublicOnly behavior across the three
 * auth statuses, with the attempted path carried in `next=`.
 */
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { beforeEach, describe, expect, it } from "vitest";

import { scriptAdapter } from "@/test/axiosTestHelper";

import { AuthProvider } from "@/context/AuthContext";
import { PublicOnly } from "@/routes/PublicOnly";
import { RequireAuth } from "@/routes/RequireAuth";

beforeEach(() => {
  localStorage.clear();
});

function ChildrenProbe(): React.ReactElement {
  return <div data-testid="children">protected content</div>;
}

function LoginStub(): React.ReactElement {
  return <div data-testid="login-page">login page</div>;
}

function DashboardStub(): React.ReactElement {
  return <div data-testid="dashboard-page">dashboard</div>;
}

function renderAt(path: string, authenticated = false, booting = false): void {
  // Drive the auth status through the real store + adapter.
  scriptAdapter([
    ...(booting
      ? [] // a hanging refresh keeps status === "booting" (never resolves)
      : [
          {
            url: "/auth/token/refresh/",
            method: "post",
            respond: () => ({
              status: 200,
              data: {
                access: "a1",
                refresh: "r1",
              },
            }),
          },
          {
            url: "/me/",
            respond: () => ({
              status: 200,
              data: { id: "u1", email: "e@x.io", is_verified: true, created_at: "t", profile_completed: true },
            }),
          },
        ]),
  ]);
  if (authenticated || booting) {
    localStorage.setItem("tjt.refresh_token", "stored-refresh");
  }
  if (authenticated && booting) {
    // A never-resolving refresh promise keeps booting; simulate by omitting
    // the script (the adapter rejects unknown calls, but boot catches them).
  }

  render(
    <AuthProvider>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route
            path="/protected"
            element={<RequireAuth />}
          >
            <Route index element={<ChildrenProbe />} />
          </Route>
          <Route path="/login" element={<PublicOnly />}>
            <Route index element={<LoginStub />} />
          </Route>
          <Route path="/dashboard" element={<DashboardStub />} />
        </Routes>
      </MemoryRouter>
    </AuthProvider>,
  );
}

describe("RequireAuth", () => {
  it("renders children for an authenticated user", async () => {
    renderAt("/protected", true);
    await screen.findByTestId("children");
    expect(screen.getByTestId("children")).toBeInTheDocument();
  });

  it("sends users with an incomplete profile to /onboarding (9.2 D1 gate)", async () => {
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
          data: { id: "u1", email: "e@x.io", is_verified: true, created_at: "t", profile_completed: false },
        }),
      },
    ]);
    localStorage.setItem("tjt.refresh_token", "stored-refresh");
    render(
      <AuthProvider>
        <MemoryRouter initialEntries={["/protected"]}>
          <Routes>
            <Route path="/protected" element={<RequireAuth />}>
              <Route index element={<ChildrenProbe />} />
            </Route>
            <Route path="/onboarding" element={<div data-testid="onboarding-page">wizard</div>} />
          </Routes>
        </MemoryRouter>
      </AuthProvider>,
    );
    await screen.findByTestId("onboarding-page");
    expect(screen.queryByTestId("children")).not.toBeInTheDocument();
  });

  it("redirects an anonymous visitor with the attempted path in next=", async () => {
    renderAt("/protected?tab=2", false);
    await screen.findByTestId("login-page");
    // MemoryRouter exposes location only via the rendered route; assert the
    // redirect happened. The next= value is asserted in the unit probe below.
    expect(screen.queryByTestId("children")).not.toBeInTheDocument();
  });

  it("shows a skeleton (not a redirect) while booting", async () => {
    // With a stored token but a refresh that never resolves, status stays
    // "booting" — the probe must show neither children nor a redirect.
    localStorage.setItem("tjt.refresh_token", "stored-refresh");
    scriptAdapter([
      {
        url: "/auth/token/refresh/",
        method: "post",
        respond: () => {
          return {
            status: 200,
            data: { access: "a1", refresh: "r1" },
          };
        },
      },
      {
        url: "/me/",
        respond: () => ({
          status: 200,
          data: { id: "u1", email: "e@x.io", is_verified: true, created_at: "t", profile_completed: true },
        }),
      },
    ]);
    // Delay resolution past the assertions with a pending promise:
    const { unmount } = render(
      <AuthProvider>
        <MemoryRouter initialEntries={["/protected"]}>
          <Routes>
            <Route path="/protected" element={<RequireAuth />}>
              <Route index element={<ChildrenProbe />} />
            </Route>
          </Routes>
        </MemoryRouter>
      </AuthProvider>,
    );
    // Synchronously after mount, booting must hold: no children rendered yet.
    expect(screen.queryByTestId("children")).not.toBeInTheDocument();
    expect(document.querySelector("[aria-busy='true']")).not.toBeNull();
    unmount();
  });
});

describe("PublicOnly", () => {
  it("renders the page for an anonymous visitor", async () => {
    renderAt("/login", false);
    await screen.findByTestId("login-page");
  });

  it("redirects an authenticated user to /dashboard", async () => {
    renderAt("/login", true);
    await screen.findByTestId("dashboard-page");
    expect(screen.queryByTestId("login-page")).not.toBeInTheDocument();
  });
});

describe("the next= parameter", () => {
  it("encodes the attempted path for the login redirect", async () => {
    let capturedSearch = "";
    function NextProbe(): React.ReactElement {
      // MemoryRouter location, not window.location (jsdom's URL is empty).
      const location = useLocation();
      capturedSearch = location.search;
      return <LoginStub />;
    }
    // Use a location-observing probe via useLocation through RequireAuth's
    // redirect: render and read the login route's search.
    localStorage.clear();
    scriptAdapter([]);
    render(
      <AuthProvider>
        <MemoryRouter initialEntries={["/timeline?view=list"]}>
          <Routes>
            <Route path="/timeline" element={<RequireAuth />}>
              <Route index element={<div>protected</div>} />
            </Route>
            <Route path="/login" element={<NextProbe />} />
          </Routes>
        </MemoryRouter>
      </AuthProvider>,
    );
    await screen.findByTestId("login-page");
    expect(capturedSearch).toBe("?next=%2Ftimeline%3Fview%3Dlist");
  });
});
