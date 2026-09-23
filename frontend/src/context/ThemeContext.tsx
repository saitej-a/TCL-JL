import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import {
  applyTheme,
  readStoredMode,
  watchSystemTheme,
  writeStoredMode,
  type ResolvedTheme,
  type ThemeMode,
} from "@/theme/theme";

interface ThemeContextValue {
  mode: ThemeMode;
  resolved: ResolvedTheme;
  setMode: (mode: ThemeMode) => void;
}

const ThemeContext = createContext<ThemeContextValue | null>(null);

interface ThemeProviderProps {
  children: ReactNode;
}

/** D5/§4.2: light|dark|system, persisted, synchronized with the root class. */
export function ThemeProvider({ children }: ThemeProviderProps) {
  const [mode, setModeState] = useState<ThemeMode>(() => readStoredMode());
  const [resolved, setResolved] = useState<ResolvedTheme>(() => applyTheme(readStoredMode()));

  const setMode = useCallback((next: ThemeMode) => {
    setModeState(next);
    writeStoredMode(next);
    setResolved(applyTheme(next));
  }, []);

  // In `system` mode, follow the OS preference live (§4.2). The event carries
  // the new value, so jsdom-stubbed matchMedia implementations that cannot
  // preserve mutable state still resolve correctly.
  useEffect(() => {
    if (mode !== "system") return;
    const unsubscribe = watchSystemTheme((dark) => {
      setResolved(dark ? "dark" : "light");
      document.documentElement.classList.toggle("dark", dark);
    });
    return unsubscribe;
  }, [mode]);

  // Re-apply on mount in case something else touched the root class.
  useEffect(() => {
    setResolved(applyTheme(mode));
  }, [mode]);

  const value = useMemo<ThemeContextValue>(
    () => ({ mode, resolved, setMode }),
    [mode, resolved, setMode],
  );

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme(): ThemeContextValue {
  const context = useContext(ThemeContext);
  if (context === null) {
    throw new Error("useTheme must be used within a ThemeProvider");
  }
  return context;
}
