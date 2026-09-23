/**
 * DashboardPage tests (Task 6): the suppression discipline (a suppressed
 * payload renders the API's message — never zeros), the D6 labelling (the
 * discussions block is the community's newest, never "your stream"), and the
 * failure path (EmptyState, not fabricated numbers).
 */
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { DashboardPage } from "@/pages/DashboardPage";
import { AuthProvider } from "@/context/AuthContext";
import { scriptAdapter } from "@/test/axiosTestHelper";

function renderDashboard(): void {
  render(
    <MemoryRouter initialEntries={["/dashboard"]}>
      <AuthProvider>
        <DashboardPage />
      </AuthProvider>
    </MemoryRouter>,
  );
}

describe("DashboardPage", () => {
  it("renders the suppression message instead of zeros when the cohort is too small", async () => {
    scriptAdapter([
      {
        url: "/dashboard/",
        respond: () => ({
          status: 200,
          data: {
            profile: { completion_percentage: 80, current_status: "WAITING_FOR_JOINING_LETTER" },
            timeline: { latest_event: { event_type: "READINESS_SURVEY", event_date: "2026-05-15" } },
            community: { unread_notifications: 2 },
            analytics: {
              data_source: "COMMUNITY_REPORTED",
              suppressed: true,
              message: "Not enough community data to display this breakdown.",
            },
          },
        }),
      },
      {
        url: "/timeline/",
        respond: () => ({ status: 200, data: { count: 0, next: null, previous: null, results: [] } }),
      },
      {
        url: "/community/posts/",
        respond: () => ({ status: 200, data: { count: 0, next: null, previous: null, results: [] } }),
      },
    ]);
    renderDashboard();
    await waitFor(() => {
      // Both the benchmark and pulse cards render the message — the page is
      // honest twice over, never zero.
      expect(
        screen.getAllByText("Not enough community data to display this breakdown.").length,
      ).toBeGreaterThanOrEqual(1);
    });
    expect(screen.queryByText("0")).not.toBeInTheDocument();
  });

  it("labels the discussions block as the community's newest (D6), never 'your stream'", async () => {
    scriptAdapter([
      {
        url: "/dashboard/",
        respond: () => ({
          status: 200,
          data: {
            profile: { completion_percentage: 100, current_status: "JOINED" },
            timeline: { latest_event: null },
            community: { unread_notifications: 0 },
            analytics: {
              data_source: "COMMUNITY_REPORTED",
              suppressed: false,
              community_waiting_count: 940,
              status_distribution: {
                REGISTERED: 10,
                INTERVIEWED: 20,
                SELECTED: 30,
                OFFER_RECEIVED: 40,
                READINESS_SURVEY: 50,
                WAITING_FOR_JOINING_LETTER: 60,
                JOINING_LETTER_RECEIVED: 70,
                JOINING_DATE_RECEIVED: 80,
                JOINED: 90,
                WITHDRAWN: 5,
                OTHER: 3,
              },
            },
          },
        }),
      },
      {
        url: "/timeline/",
        respond: () => ({ status: 200, data: { count: 0, next: null, previous: null, results: [] } }),
      },
      {
        url: "/community/posts/",
        respond: () => ({
          status: 200,
          data: {
            count: 1,
            next: null,
            previous: null,
            results: [
              {
                id: "p1",
                author: { id: "a1", display_name: "Sai T.", batch: "2025 Digital", hiring_type: "DIGITAL", region: "Hyderabad", avatar_seed: 3 },
                title: "Anyone from Hyderabad got JL?",
                body: "Asking.",
                category: "JOINING_LETTER",
                is_pinned: false,
                is_locked: false,
                is_deleted: false,
                vote_count: 42,
                comment_count: 18,
                has_voted: false,
                created_at: new Date().toISOString(),
                updated_at: new Date().toISOString(),
              },
            ],
          },
        }),
      },
    ]);
    renderDashboard();
    await waitFor(() => {
      expect(screen.getByText("Anyone from Hyderabad got JL?")).toBeInTheDocument();
    });
    expect(screen.getByText(/newest posts/i)).toBeInTheDocument();
    expect(screen.queryByText(/in your stream/i)).not.toBeInTheDocument();
  });

  it("renders the failure path as EmptyState, never fabricated numbers", async () => {
    scriptAdapter([
      {
        url: "/dashboard/",
        respond: () => ({ status: 500, data: { error: { code: "SERVER_ERROR", message: "boom" } } }),
      },
    ]);
    renderDashboard();
    await waitFor(() => {
      expect(screen.getByText("Your dashboard could not be loaded")).toBeInTheDocument();
    });
  });
});
