import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it } from "vitest";

import { Modal } from "./Modal";

function Host({ onClose }: { onClose: () => void }): React.ReactElement {
  const [open, setOpen] = useState(true);
  return (
    <div>
      <button type="button" onClick={() => setOpen(true)}>
        open
      </button>
      <Modal
        open={open}
        onClose={() => {
          setOpen(false);
          onClose();
        }}
        title="Delete Timeline Event?"
      >
        <button type="button">Cancel</button>
        <button type="button">Delete Event</button>
      </Modal>
    </div>
  );
}

describe("Modal (§6.6)", () => {
  it("renders the dialog with role=dialog and aria-modal", () => {
    render(<Host onClose={() => {}} />);
    const dialog = screen.getByRole("dialog");
    expect(dialog).toHaveAttribute("aria-modal", "true");
    expect(dialog).toHaveAttribute("aria-label", "Delete Timeline Event?");
  });

  it("Escape closes the modal", async () => {
    const user = userEvent.setup();
    let closed = false;
    render(<Host onClose={() => (closed = true)} />);
    await user.keyboard("{Escape}");
    expect(closed).toBe(true);
  });

  it("backdrop click closes the modal; clicks inside do not", async () => {
    const user = userEvent.setup();
    let closed = false;
    render(<Host onClose={() => (closed = true)} />);
    await user.click(screen.getByTestId("modal-backdrop"));
    expect(closed).toBe(true);
  });

  it("traps Tab focus inside the dialog", () => {
    render(<Host onClose={() => {}} />);
    const dialog = screen.getByRole("dialog");
    const inside = Array.from(dialog.querySelectorAll<HTMLElement>("button"));
    // Focus the last focusable element, press Tab: focus must cycle to the first.
    // (fireEvent drives the trap handler directly; jsdom has no real tab order.)
    inside[inside.length - 1]?.focus();
    fireEvent.keyDown(dialog, { key: "Tab" });
    expect(document.activeElement).toBe(inside[0]);
    // Shift+Tab from the first cycles back to the last.
    inside[0]?.focus();
    fireEvent.keyDown(dialog, { key: "Tab", shiftKey: true });
    expect(document.activeElement).toBe(inside[inside.length - 1]);
  });

  it("locks body scroll while open and restores it on close", async () => {
    const user = userEvent.setup();
    render(<Host onClose={() => {}} />);
    expect(document.body.style.overflow).toBe("hidden");
    await user.click(screen.getByRole("button", { name: "Close dialog" }));
    expect(document.body.style.overflow).toBe("");
  });
});
