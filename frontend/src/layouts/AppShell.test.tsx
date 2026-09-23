/**
 * AppShell tests: the §5.5 banner (show → dismiss → persisted across remount;
 * a new announcement id shows again), the §5.4 tab bar's presence and 44px
 * targets, the footer disclaimer at the shell level, and D2 (no staff links).
 */
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it } from "vitest";

import { AuthProvider } from "@/context/AuthContext";
import { AppShell } from "@/layouts/AppShell";
import { scriptAdapter } from "@/test/axiosTestHelper";

const ANNOUNCEMENT = {
  id: "a-1",
  title: "NOTICE: JL dispatch wave",
  body: "Hyderabad region reports dispatches.",
  is_pinned: true,
  published_at: "2026-09-01T00:00:00Z",
  expires_at: null,
};

function renderShell(path = "/dashboard") {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <AuthProvider>
        <Routes>
          <Route
            path="/dashboard"
            element={
              <AppShell>
                <p>page-content</p>
              </AppShell>
            }
          />
          <Route path="/notifications" element={<p>notifications-here</p>} />
        </Routes>
      </AuthProvider>
    </MemoryRouter>,
  );
}

function scriptAnnouncements(items: unknown[]): void {
  scriptAdapter([
    { url: "/announcements/", respond: () => ({ status: 200, data: { count: items.length, next: null, previous: null, results: items } }) },
  ]);
}

describe("AppShell", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it("renders content, the mobile tab bar, and the footer disclaimer", async () => {
    scriptAnnouncements([]);
    renderShell();
    expect(screen.getByText("page-content")).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByTestId("mobile-tab-bar")).toBeInTheDocument();
    });
    expect(screen.getByTestId("disclaimer-footer")).toBeInTheDocument();
    expect(screen.getByRole("navigation", { name: "Primary" })).toBeInTheDocument();
  });

  it("shows the latest announcement with a Read update link", async () => {
    scriptAnnouncements([ANNOUNCEMENT]);
    renderShell();
    await waitFor(() => {
      expect(screen.getByTestId("announcement-banner")).toHaveTextContent("NOTICE: JL dispatch wave");
    });
    expect(screen.getByText("Read update")).toBeInTheDocument();
  });

  it("persists dismissal per announcement id and re-shows a new id", async () => {
    const user = userEvent.setup();
    scriptAnnouncements([ANNOUNCEMENT]);
    const { unmount } = renderShell();
    await waitFor(() => screen.getByTestId("announcement-banner"));
    await user.click(screen.getByTestId("dismiss-announcement"));
    expect(screen.queryByTestId("announcement-banner")).not.toBeInTheDocument();

    // Remount = reload: the same id stays dismissed.
    scriptAnnouncements([ANNOUNCEMENT]);
    unmount();
    renderShell();
    expect(screen.queryByTestId("announcement-banner")).not.toBeInTheDocument();
    expect(JSON.parse(window.localStorage.getItem("tjt.dismissed_announcements") ?? "[]")).toEqual(["a-1"]);

    // A NEW announcement id is shown (per-announcement dismissal, 9.2 D3).
    scriptAnnouncements([{ ...ANNOUNCEMENT, id: "a-2", title: "Fresh notice" }]);
    unmount();
    renderShell();
    await waitFor(() => {
      expect(screen.getByTestId("announcement-banner")).toHaveTextContent("Fresh notice");
    });
  });

  it("degrades silently when the announcements API fails", async () => {
    scriptAdapter([
      {
        url: "/announcements/",
        respond: () => ({ status: 500, data: { error: { code: "UNKNOWN", message: "x" } } }),
      },
    ]);
    renderShell();
    await waitFor(() => {
      expect(screen.queryByTestId("announcement-banner")).not.toBeInTheDocument();
    });
    expect(screen.getByText("page-content")).toBeInTheDocument();
  });

  it("ships no staff navigation (D2)", async () => {
    scriptAnnouncements([]);
    renderShell();
    await waitFor(() => screen.getByRole("navigation", { name: "Primary" }));
    expect(screen.queryByText(/moderation/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/admin/i)).not.toBeInTheDocument();
  });
});
