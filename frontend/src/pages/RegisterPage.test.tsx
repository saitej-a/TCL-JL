/**
 * Register screen tests: client-side validation blocks bad submissions, and
 * success routes to /verify-email-pending.
 */
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { RegisterPage } from "@/pages/RegisterPage";
import { scriptAdapter } from "@/test/axiosTestHelper";

function renderRegister() {
  return render(
    <MemoryRouter initialEntries={["/register"]}>
      <Routes>
        <Route path="/register" element={<RegisterPage />} />
        <Route path="/verify-email-pending" element={<p>verify-pending-here</p>} />
        <Route path="/terms" element={<p>terms-here</p>} />
        <Route path="/privacy" element={<p>privacy-here</p>} />
      </Routes>
    </MemoryRouter>,
  );
}

async function fill(
  user: ReturnType<typeof userEvent.setup>,
  overrides: { password?: string; confirm?: string; agree?: boolean } = {},
) {
  await user.type(screen.getByLabelText("Email address"), "new@example.com");
  await user.type(screen.getByLabelText("Password", { selector: "#register-password" }), overrides.password ?? "longenough1");
  if (overrides.confirm !== "") {
    await user.type(screen.getByLabelText("Confirm password"), overrides.confirm ?? overrides.password ?? "longenough1");
  }
  if (overrides.agree !== false) {
    await user.click(screen.getByTestId("terms-checkbox"));
  }
  await user.click(screen.getByRole("button", { name: "Create account" }));
}

describe("RegisterPage", () => {
  it("blocks submission when passwords do not match", async () => {
    const user = userEvent.setup();
    const { calls } = scriptAdapter([]); // any request = failure
    renderRegister();
    await fill(user, { password: "longenough1", confirm: "different2" });
    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent("Passwords do not match.");
    });
    expect(calls).toHaveLength(0);
  });

  it("blocks submission when the terms checkbox is unchecked", async () => {
    const user = userEvent.setup();
    const { calls } = scriptAdapter([]);
    renderRegister();
    await fill(user, { agree: false });
    await waitFor(() => {
      // No navigation, no request: the button stays disabled without consent.
      expect(calls).toHaveLength(0);
      expect(screen.queryByText("verify-pending-here")).not.toBeInTheDocument();
    });
  });

  it("routes to /verify-email-pending on success", async () => {
    const user = userEvent.setup();
    scriptAdapter([
      {
        url: "/auth/register/",
        respond: () => ({
          status: 201,
          data: {
            id: "u2",
            email: "new@example.com",
            is_verified: false,
            created_at: "2026-01-01T00:00:00Z",
            profile_completed: false,
          },
        }),
      },
    ]);
    renderRegister();
    await fill(user);
    await waitFor(() => {
      expect(screen.getByText("verify-pending-here")).toBeInTheDocument();
    });
  });
});
