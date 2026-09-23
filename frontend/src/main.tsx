import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import App from "./App";
import "./index.css";

// 9.1 Task 1: minimal mount with ThemeProvider — the router, AuthProvider and
// Error Boundary arrive in Task 3 and wrap this tree.
createRoot(document.getElementById("root") as HTMLElement).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
