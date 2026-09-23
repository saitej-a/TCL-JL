import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ErrorBoundary } from "./ErrorBoundary";

function ThrowingChild(): never {
  throw new Error("boom");
}

describe("ErrorBoundary", () => {
  it("renders children when nothing throws", () => {
    render(
      <ErrorBoundary>
        <div data-testid="fine">all good</div>
      </ErrorBoundary>,
    );
    expect(screen.getByTestId("fine")).toBeInTheDocument();
  });

  it("renders 11 §4.2's copy and the reload control when a child throws", () => {
    const consoleSpy = vi.spyOn(console, "error").mockImplementation(() => {});
    render(
      <ErrorBoundary>
        <ThrowingChild />
      </ErrorBoundary>,
    );
    expect(screen.getByRole("alert")).toBeInTheDocument();
    expect(screen.getByText("Something went wrong.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Reload Application" })).toBeInTheDocument();
    expect(screen.queryByTestId("fine")).not.toBeInTheDocument();
    consoleSpy.mockRestore();
  });
});
