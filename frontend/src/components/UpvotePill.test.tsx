/**
 * UpvotePill tests (UI-03): the optimistic increment is visible while the
 * request is in flight; a failure restores the count AND the toggle and
 * fires the §6.7.1 error toast; 409 already_voted adopts the vote instead of
 * rolling back; the §6.8 class sets hold for both states.
 *
 * The pill is controlled, so the harness holds React state and feeds
 * onCommit back into props — exactly what the feed does per card.
 */
import { useState } from "react";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { ApiError } from "@/api/errors";
import { ToastProvider } from "@/components/Toast";
import { UpvotePill } from "@/components/UpvotePill";

function Harness(props: {
  request: (next: boolean) => Promise<{ has_voted?: boolean; vote_count?: number } | void>;
}) {
  const [state, setState] = useState({ voted: false, count: 42 });
  return (
    <ToastProvider>
      <UpvotePill
        voted={state.voted}
        count={state.count}
        request={props.request}
        onCommit={(commit) => setState(commit)}
      />
    </ToastProvider>
  );
}

const IDLE_MARKER = "hover:bg-brand-50";

describe("UpvotePill", () => {
  it("shows the optimistic increment while the request is in flight", async () => {
    const user = userEvent.setup();
    render(<Harness request={() => new Promise(() => undefined)} />);
    await user.click(screen.getByRole("button"));
    expect(screen.getByText("43")).toBeInTheDocument();
    expect(screen.getByRole("button")).toHaveAttribute("aria-pressed", "true");
  });

  it("rolls back the count and the toggle on failure and fires an error toast", async () => {
    const user = userEvent.setup();
    render(
      <Harness
        request={async () => {
          throw ApiError.network();
        }}
      />,
    );
    await user.click(screen.getByRole("button", { name: /Upvote/ }));
    await waitFor(() => {
      expect(screen.getByRole("button", { name: /Upvote/ })).toHaveAttribute("aria-pressed", "false");
    });
    expect(screen.getByText("42")).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent(/vote could not be saved/i);
    });
  });

  it("treats 409 already_voted as adoption, not failure", async () => {
    const user = userEvent.setup();
    render(
      <Harness
        request={async () => {
          throw new ApiError({ code: "already_voted", message: "Already voted." }, 409);
        }}
      />,
    );
    await user.click(screen.getByRole("button"));
    await waitFor(() => {
      expect(screen.getByRole("button")).toHaveAttribute("aria-pressed", "true");
    });
    expect(screen.getByText("43")).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("uses §6.8's idle and active class sets", () => {
    const { rerender } = render(
      <ToastProvider>
        <UpvotePill voted={false} count={1} request={async () => undefined} onCommit={() => undefined} />
      </ToastProvider>,
    );
    expect(screen.getByRole("button").className).toContain(IDLE_MARKER);
    rerender(
      <ToastProvider>
        <UpvotePill voted={true} count={2} request={async () => undefined} onCommit={() => undefined} />
      </ToastProvider>,
    );
    expect(screen.getByRole("button").className).toContain("bg-brand-50");
    expect(screen.getByRole("button").className).toContain("border-brand-500");
  });
});
