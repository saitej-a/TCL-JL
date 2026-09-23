import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

// With `globals: false` (Task 1's vitest config), RTL's automatic cleanup does
// not register itself — call it explicitly so renders never leak across tests.
afterEach(() => {
  cleanup();
});
