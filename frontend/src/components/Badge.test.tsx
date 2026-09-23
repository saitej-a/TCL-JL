import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Badge } from "./Badge";

describe("Badge (§4.1.4 / §6.3.1)", () => {
  it("renders a category's mapped classes", () => {
    render(<Badge.category code="JOINING_LETTER" />);
    const badge = screen.getByText("Joining Letter");
    expect(badge).toHaveClass("bg-indigo-50");
    expect(badge).toHaveClass("text-indigo-700");
    expect(badge).toHaveClass("rounded-full");
    expect(badge).toHaveClass("text-[11px]");
  });

  it("renders OFFER_LETTER with the spec's OFFER emerald treatment", () => {
    render(<Badge.category code="OFFER_LETTER" />);
    expect(screen.getByText("Offer Letter")).toHaveClass("bg-emerald-50");
  });

  it("renders a status's mapped classes including the WAITING pulse", () => {
    render(<Badge.status value="WAITING_FOR_JOINING_LETTER" />);
    const badge = screen.getByText("Waiting for JL");
    expect(badge).toHaveClass("bg-amber-100");
    expect(badge.className).toContain("animate-pulse");
  });

  it("renders JOINED with the emerald treatment", () => {
    render(<Badge.status value="JOINED" />);
    expect(screen.getByText("Joined TCS")).toHaveClass("bg-emerald-100");
  });
});
