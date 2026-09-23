import { act, fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ToastProvider, useToast } from "./Toast";

function Host({ variant }: { variant: "success" | "error" | "info" }): React.ReactElement {
  const { toast } = useToast();
  return (
    <button
      type="button"
      onClick={() => toast({ message: "Joining letter milestone added.", variant })}
    >
      fire
    </button>
  );
}

function fire(variant: "success" | "error" | "info"): void {
  render(
    <ToastProvider>
      <Host variant={variant} />
    </ToastProvider>,
  );
  fireEvent.click(screen.getByText("fire"));
}

describe("Toast (§6.7.1)", () => {
  it("auto-dismisses after 4 seconds", () => {
    vi.useFakeTimers();
    try {
      fire("success");
      expect(screen.getByTestId("toast")).toBeInTheDocument();
      act(() => {
        vi.advanceTimersByTime(4_100);
      });
      expect(screen.queryByTestId("toast")).not.toBeInTheDocument();
    } finally {
      vi.useRealTimers();
    }
  });

  it("does NOT dismiss while hovered, and dismisses after resume", () => {
    vi.useFakeTimers();
    try {
      fire("info");
      const toastEl = screen.getByTestId("toast");
      // Hover pauses the timer: past 4s the toast is still present.
      fireEvent.mouseEnter(toastEl);
      act(() => {
        vi.advanceTimersByTime(8_000);
      });
      expect(screen.getByTestId("toast")).toBeInTheDocument();
      // Leaving resumes with the remaining time; the toast then dismisses.
      fireEvent.mouseLeave(toastEl);
      act(() => {
        vi.advanceTimersByTime(4_100);
      });
      expect(screen.queryByTestId("toast")).not.toBeInTheDocument();
    } finally {
      vi.useRealTimers();
    }
  });

  it("exposes role=status for success and role=alert for error", () => {
    const { unmount } = render(
      <ToastProvider>
        <Host variant="success" />
      </ToastProvider>,
    );
    fireEvent.click(screen.getByText("fire"));
    expect(screen.getByRole("status")).toBeInTheDocument();
    unmount();

    render(
      <ToastProvider>
        <Host variant="error" />
      </ToastProvider>,
    );
    fireEvent.click(screen.getByText("fire"));
    expect(screen.getByRole("alert")).toBeInTheDocument();
  });

  it("the dismiss button removes the toast immediately", () => {
    fire("success");
    fireEvent.click(screen.getByRole("button", { name: "Dismiss notification" }));
    expect(screen.queryByTestId("toast")).not.toBeInTheDocument();
  });
});
