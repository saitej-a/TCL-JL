import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { EmptyState } from "./EmptyState";
import { ANONYMOUS_SENTINEL, IdentityPill } from "./IdentityPill";
import type { PublicAuthor } from "@/types/user";

describe("EmptyState", () => {
  it("renders headline, support line, and the default illustration", () => {
    render(
      <EmptyState
        headline="No posts yet"
        support="Be the first to start a discussion."
      />,
    );
    expect(screen.getByText("No posts yet")).toBeInTheDocument();
    expect(screen.getByText("Be the first to start a discussion.")).toBeInTheDocument();
    expect(screen.getByTestId("empty-state").querySelector("svg")).not.toBeNull();
  });

  it("renders the primary action when both label and handler are given", async () => {
    const user = userEvent.setup();
    const onAction = vi.fn();
    render(
      <EmptyState headline="Nothing here" actionLabel="Create Post" onAction={onAction} />,
    );
    await user.click(screen.getByRole("button", { name: "Create Post" }));
    expect(onAction).toHaveBeenCalledTimes(1);
  });
});

describe("IdentityPill (§6.5)", () => {
  it("renders the mask treatment for the anonymous sentinel", () => {
    const author: PublicAuthor = {
      id: "a1",
      display_name: ANONYMOUS_SENTINEL,
      batch: "2025",
      hiring_type: "Digital",
      region: "Hyderabad",
    };
    render(<IdentityPill author={author} />);
    const pill = screen.getByTestId("identity-pill");
    expect(pill.textContent).toContain("🎭");
    expect(pill.textContent).toContain(ANONYMOUS_SENTINEL);
    expect(pill.textContent).toContain("2025 • Digital • Hyderabad");
  });

  it("renders two-letter uppercase initials for a display name", () => {
    const author: PublicAuthor = {
      id: "a2",
      display_name: "Sai Teja",
      batch: "2025",
      hiring_type: "Ninja",
      region: null,
    };
    render(<IdentityPill author={author} />);
    const pill = screen.getByTestId("identity-pill");
    expect(pill.textContent).toContain("ST");
    expect(pill.textContent).toContain("2025 • Ninja");
  });

  it("never renders an email and survives all-null cohort fields", () => {
    const author: PublicAuthor = {
      id: "a3",
      display_name: "Anonymous Candidate",
      batch: null,
      hiring_type: null,
      region: null,
    };
    render(<IdentityPill author={author} />);
    const pill = screen.getByTestId("identity-pill");
    expect(pill.textContent).not.toContain("@");
    expect(pill.textContent).not.toContain("undefined");
    expect(pill.textContent).not.toContain("null");
  });

  it("is deterministic: the same name yields the same pastel across renders", () => {
    const author: PublicAuthor = {
      id: "a4",
      display_name: "Priya Sharma",
      batch: null,
      hiring_type: null,
      region: null,
    };
    const { rerender } = render(<IdentityPill author={author} />);
    const avatarClass = screen.getByTestId("identity-pill").querySelector("div")?.className;
    rerender(<IdentityPill author={author} />);
    expect(screen.getByTestId("identity-pill").querySelector("div")?.className).toBe(avatarClass);
  });
});
