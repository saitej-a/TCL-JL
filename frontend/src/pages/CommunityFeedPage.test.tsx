/**
 * CommunityFeedPage tests (§7.6): category selection reaches the API as a
 * query param, the empty state renders for an empty result set, and the
 * optimistic vote flow ends in the reconciled committed state. Adapter-swap
 * failure paths stay the 9.1/9.2 seam — no mocking dependency.
 */
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { CommunityFeedPage } from "@/pages/CommunityFeedPage";
import { ToastProvider } from "@/components/Toast";
import { AuthProvider } from "@/context/AuthContext";
import { scriptAdapter } from "@/test/axiosTestHelper";

const POST = {
  id: "p1",
  author: {
    id: "a1",
    display_name: "Anonymous Candidate",
    batch: "2025 Digital",
    hiring_type: "DIGITAL",
    region: "Hyderabad",
    avatar_seed: 3,
  },
  title: "Anyone from Hyderabad got JL?",
  body: "Asking for the August batch.",
  category: "JOINING_LETTER",
  is_pinned: false,
  is_locked: false,
  is_deleted: false,
  vote_count: 41,
  comment_count: 7,
  has_voted: false,
  created_at: "2026-09-20T10:00:00Z",
  updated_at: "2026-09-20T10:00:00Z",
};

function listBody(results: unknown[]) {
  return { status: 200, data: { count: results.length, next: null, previous: null, results } };
}

function renderFeed(initialEntry = "/community") {
  return render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <AuthProvider>
        <ToastProvider>
          <CommunityFeedPage />
        </ToastProvider>
      </AuthProvider>
    </MemoryRouter>,
  );
}

describe("CommunityFeedPage", () => {
  // The adapter is a cursor over one step per logical call. StrictMode lives in
  // main.tsx only — the test renderer mounts without it — so effects fire ONCE
  // and the script carries a single batch of initial GETs. (Scripting the
  // double batch here silently consumed the wrong step: the filtered request
  // landed on the mount step and the vote POST landed on a GET.)
  it("issues the request with the selected category", async () => {
    const user = userEvent.setup();
    const urls: string[] = [];
    scriptAdapter([
      // Initial load (one batch: mount effect)
      { url: "/community/posts/", respond: () => listBody([POST]) },
      { url: "/announcements/", respond: () => listBody([]) },
      // Selection triggers a filtered GET
      {
        url: "/community/posts/",
        respond: (config) => {
          urls.push(JSON.stringify(config.params));
          return listBody([POST]);
        },
      },
    ]);
    renderFeed();
    await screen.findByText("Anyone from Hyderabad got JL?");
    await user.click(screen.getByRole("radio", { name: "Joining Letter" }));
    await waitFor(() => {
      expect(urls.some((url) => url.includes("JOINING_LETTER"))).toBe(true);
    });
  });

  it("renders the empty state for an empty result set", async () => {
    scriptAdapter([
      { url: "/community/posts/", respond: () => listBody([]) },
      { url: "/announcements/", respond: () => listBody([]) },
    ]);
    renderFeed();
    // §7.6's pinned empty-state copy.
    await screen.findByText("No discussions found in this category.");
    expect(
      screen.getByText("Be the first candidate to share an update or question."),
    ).toBeInTheDocument();
  });

  it("renders §7.6's heading, search copy, pinned announcement, and paging footer", async () => {
    scriptAdapter([
      { url: "/community/posts/", respond: () => listBody([POST]) },
      {
        url: "/announcements/",
        respond: () => ({
          status: 200,
          data: {
            count: 1,
            next: null,
            previous: null,
            results: [
              {
                id: "an1",
                title: "Important Community Guidelines & Scam Prevention Advice",
                body: "TCS never charges money for training, equipment, or joining letter issuance.",
                is_pinned: true,
                published_at: "2026-09-22T10:00:00Z",
                expires_at: null,
              },
            ],
          },
        }),
      },
    ]);
    renderFeed();
    expect(await screen.findByText("Community Discussions")).toBeInTheDocument();
    expect(screen.getByLabelText("Search posts")).toHaveAttribute(
      "placeholder",
      "Search posts by keyword, location, or batch...",
    );
    expect(screen.getByText("📌 Pinned announcement")).toBeInTheDocument();
    expect(
      screen.getByText("Important Community Guidelines & Scam Prevention Advice"),
    ).toBeInTheDocument();
    // §7.6's paging footer, over the real envelope: 1 post, page 1 of 1.
    expect(screen.getByText("Showing 1-1 of 1 posts")).toBeInTheDocument();
    expect(screen.getByText("Page 1 of 1")).toBeInTheDocument();
  });

  it("shows the optimistic count, then the reconciled committed count", async () => {
    const user = userEvent.setup();
    const { calls } = scriptAdapter([
      // Initial load (one batch: mount effect)
      { url: "/community/posts/", respond: () => listBody([POST]) },
      { url: "/announcements/", respond: () => listBody([]) },
      // Click triggers upvote POST
      {
        url: "/vote/",
        method: "post",
        respond: () => ({
          status: 201,
          data: { id: "p1", vote_count: 42, has_voted: true, is_pinned: false, is_locked: false },
        }),
      },
    ]);
    renderFeed();
    await screen.findByText("41");
    await user.click(screen.getByRole("button", { name: /Upvote/ }));
    await waitFor(() => {
      expect(calls.some((call) => String(call.url).includes("/vote/"))).toBe(true);
    });
    // The reconciled count must survive the overlay clearing — reading it back
    // off `post.vote_count` (the list snapshot) silently reverted a successful
    // vote to the pre-vote number.
    await waitFor(() => {
      expect(screen.getByText("42")).toBeInTheDocument();
    });
    expect(screen.queryByText("41")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Upvoted/ })).toHaveAttribute("aria-pressed", "true");
  });
});
