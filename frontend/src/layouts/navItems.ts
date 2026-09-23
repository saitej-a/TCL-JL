/**
 * The §7.4 navigation vocabulary, shared by the sidebar and the tab bar.
 * D2: no staff items — staff surfaces stay unlinked (server-side enforcement
 * is the authority, 04 §113).
 */
export const NAV_ITEMS = [
  { to: "/dashboard", label: "Dashboard" },
  { to: "/timeline", label: "Timeline" },
  { to: "/community", label: "Community" },
  { to: "/analytics", label: "Analytics" },
  { to: "/notifications", label: "Alerts" },
  { to: "/settings", label: "Settings" },
] as const;

/** The five §5.4 mobile tabs (Analytics is not in the mobile bar). */
export const MOBILE_TABS = [
  { to: "/dashboard", label: "Dashboard" },
  { to: "/timeline", label: "Timeline" },
  { to: "/community", label: "Community" },
  { to: "/notifications", label: "Alerts" },
  { to: "/settings", label: "Settings" },
] as const;
