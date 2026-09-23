/**
 * Onboarding wizard tests: first visit starts at step 1 (profile 404),
 * step 1 POSTs the real field names, step 2 PATCHes the status side-channel,
 * step 3 requires the accuracy confirmation, and finishing calls /me/ (the
 * truthful gate release).
 */
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { AuthProvider } from "@/context/AuthContext";
import { OnboardingPage } from "@/pages/OnboardingPage";
import { scriptAdapter } from "@/test/axiosTestHelper";

const PROFILE_404 = {
  status: 404,
  data: { error: { code: "PROFILE_NOT_FOUND", message: "No profile yet." } },
};

const PROFILE_CREATED = {
  id: "p1",
  display_name: "Sai",
  public_identity_mode: "DISPLAY_NAME",
  batch: "2025",
  hiring_type: "DIGITAL",
  region: "Hyderabad",
  interview_center: "",
  interview_date: null,
  joining_location: "",
  current_status: "OFFER_RECEIVED",
  offer_letter_date: "2025-03-15",
  expected_joining_date: null,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

const ME_COMPLETE = {
  id: "u1",
  email: "c@example.com",
  is_verified: true,
  created_at: "2026-01-01T00:00:00Z",
  profile_completed: true,
};

function renderWizard() {
  return render(
    <MemoryRouter initialEntries={["/onboarding"]}>
      <AuthProvider>
        <Routes>
          <Route path="/onboarding" element={<OnboardingPage />} />
          <Route path="/dashboard" element={<p>dashboard-here</p>} />
        </Routes>
      </AuthProvider>
    </MemoryRouter>,
  );
}

describe("OnboardingPage", () => {
  it("starts at step 1 when no profile exists (404)", async () => {
    scriptAdapter([
      { url: "/profile/", respond: () => PROFILE_404 },
    ]);
    renderWizard();
    await waitFor(() => {
      expect(screen.getByText("Tell us about your offer")).toBeInTheDocument();
    });
    expect(screen.getByText(/Step 1 of 3/)).toBeInTheDocument();
  });

  it("persists step 1 with the real field names, then advances to step 2", async () => {
    const user = userEvent.setup();
    const { calls } = scriptAdapter([
      { url: "/profile/", method: "GET", respond: () => PROFILE_404 },
      { url: "/profile/", method: "POST", respond: () => ({ status: 201, data: PROFILE_CREATED }) },
    ]);
    renderWizard();
    await waitFor(() => {
      expect(screen.getByLabelText("Community display name")).toBeInTheDocument();
    });
    await user.type(screen.getByLabelText("Community display name"), "Sai");
    await user.type(screen.getByLabelText("Region of joining"), "Hyderabad");
    await user.click(screen.getByRole("radio", { name: "digital" }));
    await user.type(screen.getByLabelText("Offer letter date"), "2025-03-15");
    await user.click(screen.getByRole("button", { name: "Continue" }));

    await waitFor(() => {
      expect(screen.getByText(/Step 2 of 3/)).toBeInTheDocument();
    });
    const post = calls.find((c) => c.method?.toLowerCase() === "post");
    expect(post).toBeDefined();
    const body = JSON.parse(String(post?.data));
    expect(body).toMatchObject({
      display_name: "Sai",
      hiring_type: "DIGITAL",
      region: "Hyderabad",
      batch: "2025",
      offer_letter_date: "2025-03-15",
    });
  });

  it("persists step 2 as a timeline event (walk-the-chain, 4.1 D1)", async () => {
    const user = userEvent.setup();
    const { calls } = scriptAdapter([
      { url: "/profile/", method: "GET", respond: () => PROFILE_404 },
      { url: "/profile/", method: "POST", respond: () => ({ status: 201, data: PROFILE_CREATED }) },
      {
        url: "/timeline/",
        method: "POST",
        respond: () => ({
          status: 201,
          data: {
            id: "t1",
            event_type: "OFFER_LETTER",
            event_date: "2025-03-20",
            description: "x",
            is_verified: false,
            created_at: "x",
          },
        }),
      },
      { url: "/me/", method: "GET", respond: () => ({ status: 200, data: ME_COMPLETE }) },
    ]);
    renderWizard();
    await waitFor(() => screen.getByLabelText("Community display name"));
    await user.type(screen.getByLabelText("Community display name"), "Sai");
    await user.type(screen.getByLabelText("Region of joining"), "Hyderabad");
    await user.type(screen.getByLabelText("Offer letter date"), "2025-03-15");
    await user.click(screen.getByRole("button", { name: "Continue" }));

    await waitFor(() => screen.getByText("Where are you in the process?"));
    await user.click(screen.getByRole("radio", { name: /Offer received/ }));
    await user.type(screen.getByLabelText("When did this happen?"), "2025-03-20");
    await user.click(screen.getByRole("button", { name: "Continue" }));

    await waitFor(() => screen.getByText("Review your details"));
    const post = calls.filter((c) => c.method?.toLowerCase() === "post");
    const timelinePost = post.find((c) => String(c.url).endsWith("/timeline/"));
    expect(timelinePost).toBeDefined();
    expect(JSON.parse(String(timelinePost?.data))).toMatchObject({
      event_type: "OFFER_LETTER",
      event_date: "2025-03-20",
    });
  });

  it("requires the accuracy confirmation before finishing, then releases the gate", async () => {
    const user = userEvent.setup();
    const { calls } = scriptAdapter([
      { url: "/profile/", method: "GET", respond: () => PROFILE_404 },
      { url: "/profile/", method: "POST", respond: () => ({ status: 201, data: PROFILE_CREATED }) },
      {
        url: "/timeline/",
        method: "POST",
        respond: () => ({
          status: 201,
          data: {
            id: "t1",
            event_type: "OFFER_LETTER",
            event_date: "2025-03-20",
            description: "x",
            is_verified: false,
            created_at: "x",
          },
        }),
      },
      { url: "/me/", method: "GET", respond: () => ({ status: 200, data: ME_COMPLETE }) },
    ]);
    renderWizard();
    await waitFor(() => screen.getByLabelText("Community display name"));
    await user.type(screen.getByLabelText("Community display name"), "Sai");
    await user.type(screen.getByLabelText("Region of joining"), "Hyderabad");
    await user.type(screen.getByLabelText("Offer letter date"), "2025-03-15");
    await user.click(screen.getByRole("button", { name: "Continue" }));
    await waitFor(() => screen.getByText("Where are you in the process?"));
    await user.type(screen.getByLabelText("When did this happen?"), "2025-03-20");
    await user.click(screen.getByRole("button", { name: "Continue" }));
    await waitFor(() => screen.getByText("Review your details"));

    const finishButton = screen.getByRole("button", { name: /Finish and go to dashboard/ });
    expect(finishButton).toBeDisabled(); // T-09.2 gate: confirm first

    await user.click(screen.getByTestId("confirm-accuracy"));
    expect(finishButton).toBeEnabled();
    await user.click(finishButton);

    await waitFor(() => {
      expect(screen.getByText("dashboard-here")).toBeInTheDocument();
    });
    expect(calls.some((c) => String(c.url).endsWith("/me/"))).toBe(true);
  });
});
