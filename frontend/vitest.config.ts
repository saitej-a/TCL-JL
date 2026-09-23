import { fileURLToPath, URL } from "node:url";

import { defineConfig } from "vitest/config";

// D8 (CONTEXT): headless Vitest + RTL, no mocking dependency — the API client's
// interceptor is tested by swapping the axios instance's adapter instead.
export default defineConfig({
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    globals: false,
    css: false,
  },
});
