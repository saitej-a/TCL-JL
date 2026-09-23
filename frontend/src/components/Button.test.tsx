import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Button } from "./Button";

describe("Button (§6.1)", () => {
  it("renders each variant's distinguishing class", () => {
    render(
      <>
        <Button variant="primary">p</Button>
        <Button variant="secondary">s</Button>
        <Button variant="outline">o</Button>
        <Button variant="ghost">g</Button>
        <Button variant="danger">d</Button>
      </>,
    );
    expect(screen.getByText("p")).toHaveClass("bg-brand-600");
    expect(screen.getByText("s")).toHaveClass("bg-slate-100");
    expect(screen.getByText("o")).toHaveClass("border-slate-300");
    expect(screen.getByText("g")).toHaveClass("bg-transparent");
    expect(screen.getByText("d")).toHaveClass("bg-rose-600");
  });

  it("loading disables the button and shows the spinner", () => {
    render(<Button loading>Saving</Button>);
    const button = screen.getByRole("button", { name: "Saving" });
    expect(button).toBeDisabled();
    expect(button.querySelector(".animate-spin")).not.toBeNull();
  });

  it("disabled applies the §6.1.3 pointer-events-none guard", () => {
    render(<Button disabled>Locked</Button>);
    expect(screen.getByRole("button", { name: "Locked" })).toHaveClass("pointer-events-none");
    expect(screen.getByRole("button", { name: "Locked" })).toBeDisabled();
  });

  it("sizes map to the §6.1.2 heights", () => {
    render(
      <>
        <Button size="sm">sm</Button>
        <Button size="md">md</Button>
        <Button size="lg">lg</Button>
      </>,
    );
    expect(screen.getByText("sm")).toHaveClass("h-8");
    expect(screen.getByText("md")).toHaveClass("h-10");
    expect(screen.getByText("lg")).toHaveClass("h-12");
  });
});
