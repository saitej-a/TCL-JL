/**
 * Landing page tests: stats render on resolve, the failure path renders the
 * fallback (never fabricated numbers), and the CTAs route correctly.
 */
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { LandingPage } from "@/pages/LandingPage";
import { scriptAdapter } from "@/test/axiosTestHelper";

function renderLanding() {
  return render(
    <MemoryRouter initialEntries={["/"]}>
      <LandingPage />
    </MemoryRouter>,
  );
}

describe("LandingPage", () => {
  it("renders the live stats from /public/stats/", async () => {
    scriptAdapter([
      {
        url: "/public/stats/",
        respond: () => ({
          status: 200,
          data: {
            data_source: "COMMUNITY_REPORTED",
            disclaimer: "Community-reported",
            registered_candidates: 1248,
            community_posts: 42,
            timeline_events: 220,
          },
        }),
      },
    ]);
    renderLanding();
    await waitFor(() => {
      expect(screen.getByText("1,248")).toBeInTheDocument();
    });
    expect(screen.getByText("Community posts")).toBeInTheDocument();
    expect(screen.getByText("220")).toBeInTheDocument();
  });

  it("renders the fallback on API failure — never fabricated numbers", async () => {
    scriptAdapter([
      {
        url: "/public/stats/",
        respond: () => ({ status: 500, data: { error: { code: "UNKNOWN", message: "boom" } } }),
      },
    ]);
    renderLanding();
    await waitFor(() => {
      expect(screen.getByRole("status")).toHaveTextContent("unavailable");
    });
    expect(screen.queryByText("1,248")).not.toBeInTheDocument();
  });

  it("links the CTAs to /register and /login", () => {
    scriptAdapter([
      { url: "/public/stats/", respond: () => ({ status: 500, data: {} }) },
    ]);
    renderLanding();
    expect(screen.getByRole("link", { name: "Create account" })).toHaveAttribute("href", "/register");
    expect(screen.getByRole("link", { name: "Sign in" })).toHaveAttribute("href", "/login");
  });

  it("carries the footer disclaimer", () => {
    scriptAdapter([
      { url: "/public/stats/", respond: () => ({ status: 500, data: {} }) },
    ]);
    renderLanding();
    expect(screen.getByTestId("disclaimer-footer")).toBeInTheDocument();
  });
});
