import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { Input } from "./Input";
import { Textarea } from "./Textarea";

describe("Input (§6.2.1)", () => {
  it("links error text via aria-describedby", () => {
    render(<Input label="Email" errorText="Enter a valid email address." />);
    const input = screen.getByLabelText("Email");
    expect(input).toHaveAttribute("aria-invalid", "true");
    const describedBy = input.getAttribute("aria-describedby") ?? "";
    const errorEl = screen.getByText("Enter a valid email address.");
    expect(describedBy).toContain(errorEl.id);
  });

  it("links helper text via aria-describedby when no error exists", () => {
    render(<Input label="Email" helperText="We'll never share your email address publicly." />);
    const input = screen.getByLabelText("Email");
    const describedBy = input.getAttribute("aria-describedby") ?? "";
    const helperEl = screen.getByText("We'll never share your email address publicly.");
    expect(describedBy).toContain(helperEl.id);
  });

  it("the reveal toggle flips the input type and keeps its aria-label", async () => {
    const user = userEvent.setup();
    render(<Input label="Password" type="password" />);
    const toggle = screen.getByRole("button", { name: "Toggle password visibility" });
    const input = screen.getByLabelText("Password");
    expect(input).toHaveAttribute("type", "password");
    await user.click(toggle);
    expect(input).toHaveAttribute("type", "text");
    expect(screen.getByRole("button", { name: "Toggle password visibility" })).toBeInTheDocument();
    await user.click(toggle);
    expect(input).toHaveAttribute("type", "password");
  });
});

describe("Textarea (§6.2.1)", () => {
  it("renders the live character tally with locale grouping", () => {
    render(<Textarea label="Body" maxLength={2000} value={"a".repeat(1240)} onChange={() => {}} />);
    expect(screen.getByText("1,240 / 2,000 characters")).toBeInTheDocument();
  });

  it("turns amber at ≥90% and rose past the cap", () => {
    const { rerender } = render(
      <Textarea label="Body" maxLength={2000} value={"a".repeat(1800)} onChange={() => {}} />,
    );
    const amberTally = screen.getByText("1,800 / 2,000 characters");
    expect(amberTally.className).toContain("text-amber-600");

    // A controlled value can programmatically exceed the cap (e.g. after a
    // maxLength change); the tally must read it as rose.
    rerender(
      <Textarea label="Body" maxLength={2000} value={"a".repeat(2100)} onChange={() => {}} />,
    );
    const roseTally = screen.getByText("2,100 / 2,000 characters");
    expect(roseTally.className).toContain("text-rose-600");
  });

  it("clamps the value via maxLength", async () => {
    const user = userEvent.setup();
    let current = "";
    function Host(): React.ReactElement {
      return (
        <Textarea
          label="Body"
          maxLength={5}
          value={current}
          onChange={(event) => {
            current = event.target.value;
          }}
        />
      );
    }
    render(<Host />);
    const box = screen.getByLabelText("Body") as HTMLTextAreaElement;
    await user.type(box, "toolongvalue");
    expect(box.value.length).toBeLessThanOrEqual(5);
  });
});
