/**
 * TimelinePage tests (Task 7): create posts exactly the three writable
 * fields (never auto_update_status), a rejected date renders the server's
 * message inline verbatim, and delete requires confirmation before DELETE.
 *
 * Script steps must match the page's actual request order: the initial load
 * fires GET /timeline/ (refresh) and GET /profile/ (status) via Promise.all.
 */
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { TimelinePage } from "@/pages/TimelinePage";
import { ToastProvider } from "@/components/Toast";
import { scriptAdapter } from "@/test/axiosTestHelper";

const PROFILE = {
  id: "prof-1",
  display_name: "Sai T.",
  public_identity_mode: "DISPLAY_NAME",
  batch: "2025 Digital",
  hiring_type: "DIGITAL",
  region: "Hyderabad",
  interview_center: "Hyderabad",
  interview_date: null,
  joining_location: "Hyderabad",
  current_status: "WAITING_FOR_JOINING_LETTER",
  offer_letter_date: null,
  expected_joining_date: null,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

const EVENT = {
  id: "evt-1",
  event_type: "INTERVIEW",
  event_date: "2026-04-23",
  description: "Hyderabad center.",
  is_verified: true,
  created_at: "2026-04-23T00:00:00Z",
};

function listResponse(events: unknown[]) {
  return { status: 200, data: { count: events.length, next: null, previous: null, results: events } };
}

function renderTimeline() {
  return render(
    <MemoryRouter initialEntries={["/timeline"]}>
      <ToastProvider>
        <TimelinePage />
      </ToastProvider>
    </MemoryRouter>,
  );
}

describe("TimelinePage", () => {
  it("posts exactly the three writable fields on create", async () => {
    const user = userEvent.setup();
    const bodies: string[] = [];
    scriptAdapter([
      { url: "/timeline/", method: "get", respond: () => listResponse([]) },
      { url: "/profile/", respond: () => ({ status: 200, data: PROFILE }) },
      {
        url: "/timeline/",
        method: "post",
        respond: (config) => {
          bodies.push(String(config.data));
          return { status: 201, data: EVENT };
        },
      },
      { url: "/timeline/", method: "get", respond: () => listResponse([EVENT]) },
      { url: "/profile/", respond: () => ({ status: 200, data: PROFILE }) },
    ]);
    renderTimeline();
    const addButton = await screen.findByRole("button", { name: /Add Milestone Event/i });
    await user.click(addButton);
    const saveButton = await screen.findByRole("button", { name: /Add Event/i });
    await user.click(saveButton);
    await waitFor(() => expect(bodies).toHaveLength(1));
    const body = JSON.parse(bodies[0] ?? "{}");
    expect(Object.keys(body).sort()).toEqual(["description", "event_date", "event_type"]);
  });

  it("renders a rejected date's server message inline", async () => {
    const user = userEvent.setup();
    const SERVER_MESSAGE = "event_date cannot be more than 730 days in the future.";
    scriptAdapter([
      { url: "/timeline/", method: "get", respond: () => listResponse([]) },
      { url: "/profile/", respond: () => ({ status: 200, data: PROFILE }) },
      {
        url: "/timeline/",
        method: "post",
        respond: () => ({ status: 400, data: { event_date: [SERVER_MESSAGE] } }),
      },
    ]);
    renderTimeline();
    const addButton = await screen.findByRole("button", { name: /Add Milestone Event/i });
    await user.click(addButton);
    const saveButton = await screen.findByRole("button", { name: /Add Event/i });
    await user.click(saveButton);
    await waitFor(() => expect(screen.getByText(SERVER_MESSAGE)).toBeInTheDocument());
  });

  it("requires confirmation before DELETE", async () => {
    const user = userEvent.setup();
    const deletes: string[] = [];
    scriptAdapter([
      { url: "/timeline/", method: "get", respond: () => listResponse([EVENT]) },
      { url: "/profile/", respond: () => ({ status: 200, data: PROFILE }) },
      {
        url: "/evt-1/",
        method: "delete",
        respond: (config) => {
          deletes.push(String(config.url));
          return { status: 204, data: {} };
        },
      },
      { url: "/timeline/", method: "get", respond: () => listResponse([]) },
    ]);
    renderTimeline();
    const deleteButtons = await screen.findAllByRole("button", { name: "Delete" });
    await user.click(deleteButtons[0] as HTMLElement);
    const confirmButton = await screen.findByRole("button", { name: /Delete event/i });
    await user.click(confirmButton);
    await waitFor(() => expect(deletes).toHaveLength(1));
  });
});
