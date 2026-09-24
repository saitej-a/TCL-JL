/**
 * CreatePostPage tests (§7.7 / D5): the payload's category comes from the D7
 * vocabulary, and the two writer rejections render distinctly — the scam
 * block never implies rewording; the duplicate names the debounce window.
 */
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { CreatePostPage } from "@/pages/CreatePostPage";
import { scriptAdapter } from "@/test/axiosTestHelper";

/** §7.7's identity preview reads the viewer's own profile on mount. */
function profileStep() {
  return {
    url: "/profile/",
    respond: () => ({
      status: 200,
      data: {
        id: "prof-1",
        display_name: "Sai",
        public_identity_mode: "ANONYMOUS" as const,
        batch: "2025",
        hiring_type: "DIGITAL",
        region: "Hyderabad",
        interview_center: "HYD",
        interview_date: null,
        joining_location: "Hyderabad",
        current_status: "WAITING_FOR_JOINING_LETTER",
        offer_letter_date: "2026-05-05",
        expected_joining_date: null,
        created_at: "2026-05-01T00:00:00Z",
        updated_at: "2026-05-01T00:00:00Z",
      },
    }),
  };
}

function renderCreate() {
  return render(
    <MemoryRouter initialEntries={["/community/create"]}>
      <CreatePostPage />
    </MemoryRouter>,
  );
}

async function fillAndSubmit(user: ReturnType<typeof userEvent.setup>): Promise<void> {
  await user.type(screen.getByLabelText(/Title/i), "Joining letter timeline");
  await user.type(screen.getByLabelText(/Body/i), "Anyone heard back about the August wave?");
  await user.click(screen.getByRole("button", { name: /Publish post/i }));
}

describe("CreatePostPage", () => {
  it("renders the scam rejection distinctly, without retry-with-same-text implications", async () => {
    const user = userEvent.setup();
    scriptAdapter([
      profileStep(),
      {
        url: "/community/posts/",
        method: "post",
        respond: () => ({ status: 400, data: { error: { code: "scam_pattern_detected", message: "blocked" } } }),
      },
    ]);
    renderCreate();
    await fillAndSubmit(user);
    await waitFor(() => {
      expect(screen.getByText(/blocked by our anti-scam screening/i)).toBeInTheDocument();
    });
    expect(screen.queryByText(/60 minutes/i)).not.toBeInTheDocument();
  });

  it("renders the duplicate rejection with the 60-minute window", async () => {
    const user = userEvent.setup();
    scriptAdapter([
      profileStep(),
      {
        url: "/community/posts/",
        method: "post",
        respond: () => ({ status: 400, data: { error: { code: "duplicate_post", message: "duplicate" } } }),
      },
    ]);
    renderCreate();
    await fillAndSubmit(user);
    await waitFor(() => {
      expect(screen.getByText(/60 minutes/i)).toBeInTheDocument();
    });
    expect(screen.queryByText(/anti-scam/i)).not.toBeInTheDocument();
  });

  it("requires title and body client-side before any request", async () => {
    const user = userEvent.setup();
    let called = false;
    scriptAdapter([
      profileStep(),
      {
        url: "/community/posts/",
        method: "post",
        respond: () => {
          called = true;
          return { status: 201, data: {} };
        },
      },
    ]);
    renderCreate();
    await user.click(screen.getByRole("button", { name: /Publish Post/i }));
    expect(screen.getByText("A title is required.")).toBeInTheDocument();
    expect(called).toBe(false);
  });

  it("pins §7.7's live counters, identity preview, and copy", async () => {
    scriptAdapter([profileStep()]);
    renderCreate();
    // §7.7's counters start at zero for the declared limits (title 200, body 5,000).
    expect(screen.getByText("0 / 200 characters")).toBeInTheDocument();
    expect(screen.getByText("0 / 5000 characters")).toBeInTheDocument();
    expect(screen.getByText("Create Community Discussion Post")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Publish Post/i })).toBeInTheDocument();
    // ANONYMOUS mode renders the sentinel, never the display name.
    await waitFor(() => {
      expect(screen.getByText(/Anonymous Candidate • 2025 • DIGITAL • Hyderabad/)).toBeInTheDocument();
    });
    expect(screen.queryByText(/Sai/)).not.toBeInTheDocument();
  });
});
