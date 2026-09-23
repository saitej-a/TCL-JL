import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ThemeProvider, useTheme } from "./ThemeContext";

let matchMediaListeners: Set<(event: MediaQueryListEvent) => void>;

function fireSystemChange(dark: boolean): void {
  const event = { matches: dark } as MediaQueryListEvent;
  matchMediaListeners.forEach((listener) => listener(event));
}

beforeEach(() => {
  matchMediaListeners = new Set();
  vi.stubGlobal(
    "matchMedia",
    vi.fn().mockImplementation((query: string) => ({
      matches: false,
      media: query,
      addEventListener: (_: string, listener: (event: MediaQueryListEvent) => void) => {
        matchMediaListeners.add(listener);
      },
      removeEventListener: (_: string, listener: (event: MediaQueryListEvent) => void) => {
        matchMediaListeners.delete(listener);
      },
    })),
  );
  localStorage.clear();
});

afterEach(() => {
  vi.unstubAllGlobals();
  document.documentElement.classList.remove("dark");
});

function ModeProbe(): React.ReactElement {
  const { mode, resolved, setMode } = useTheme();
  return (
    <div>
      <span data-testid="mode">{mode}</span>
      <span data-testid="resolved">{resolved}</span>
      <button onClick={() => setMode("dark")}>dark</button>
      <button onClick={() => setMode("light")}>light</button>
      <button onClick={() => setMode("system")}>system</button>
    </div>
  );
}

describe("ThemeProvider", () => {
  it("defaults to system and applies no dark class when the OS is light", () => {
    render(
      <ThemeProvider>
        <ModeProbe />
      </ThemeProvider>,
    );
    expect(screen.getByTestId("mode")).toHaveTextContent("system");
    expect(screen.getByTestId("resolved")).toHaveTextContent("light");
    expect(document.documentElement.classList.contains("dark")).toBe(false);
  });

  it("applies the dark class on <html> for dark mode and removes it for light", async () => {
    const user = userEvent.setup();
    render(
      <ThemeProvider>
        <ModeProbe />
      </ThemeProvider>,
    );
    await user.click(screen.getByText("dark"));
    expect(document.documentElement.classList.contains("dark")).toBe(true);
    expect(localStorage.getItem("theme")).toBe("dark");
    await user.click(screen.getByText("light"));
    expect(document.documentElement.classList.contains("dark")).toBe(false);
    expect(localStorage.getItem("theme")).toBe("light");
  });

  it("follows a matchMedia change while in system mode", async () => {
    const user = userEvent.setup();
    render(
      <ThemeProvider>
        <ModeProbe />
      </ThemeProvider>,
    );
    await user.click(screen.getByRole("button", { name: "system" }));
    act(() => {
      fireSystemChange(true);
    });
    expect(screen.getByTestId("resolved")).toHaveTextContent("dark");
    expect(document.documentElement.classList.contains("dark")).toBe(true);
  });

  it("restores a persisted mode from localStorage on mount", () => {
    localStorage.setItem("theme", "dark");
    render(
      <ThemeProvider>
        <ModeProbe />
      </ThemeProvider>,
    );
    expect(screen.getByTestId("mode")).toHaveTextContent("dark");
    expect(document.documentElement.classList.contains("dark")).toBe(true);
  });
});
