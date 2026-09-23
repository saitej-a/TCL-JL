/**
 * Theme mode plumbing (Task 1, D5/§4.2): `light | dark | system` persisted in
 * `localStorage('theme')`, applied as the Tailwind `dark` class on
 * `<html>`, with `system` following `matchMedia` live.
 */

export type ThemeMode = "light" | "dark" | "system";
export type ResolvedTheme = "light" | "dark";

export const THEME_STORAGE_KEY = "theme";

const DARK_CLASS = "dark";
const MODES: ThemeMode[] = ["light", "dark", "system"];

function isThemeMode(value: unknown): value is ThemeMode {
  return typeof value === "string" && (MODES as string[]).includes(value);
}

export function prefersDark(): boolean {
  return window.matchMedia("(prefers-color-scheme: dark)").matches;
}

/** Subscribe to the OS preference while in `system` mode; unsubscribe fn returned. */
export function watchSystemTheme(onChange: (dark: boolean) => void): () => void {
  const media = window.matchMedia("(prefers-color-scheme: dark)");
  const handler = (event: MediaQueryListEvent): void => onChange(event.matches);
  media.addEventListener("change", handler);
  return () => media.removeEventListener("change", handler);
}

export function readStoredMode(): ThemeMode {
  try {
    const raw = localStorage.getItem(THEME_STORAGE_KEY);
    return isThemeMode(raw) ? raw : "system";
  } catch {
    // Storage disabled — degrade to following the OS, never crash.
    return "system";
  }
}

export function writeStoredMode(mode: ThemeMode): void {
  try {
    localStorage.setItem(THEME_STORAGE_KEY, mode);
  } catch {
    // Storage disabled — the in-memory mode still drives this session.
  }
}

export function resolveTheme(mode: ThemeMode): ResolvedTheme {
  return mode === "system" ? (prefersDark() ? "dark" : "light") : mode;
}

export function applyTheme(mode: ThemeMode): ResolvedTheme {
  const resolved = resolveTheme(mode);
  document.documentElement.classList.toggle(DARK_CLASS, resolved === "dark");
  return resolved;
}
