import { RouterProvider } from "react-router-dom";

import { ErrorBoundary } from "@/components/ErrorBoundary";
import { AuthProvider } from "@/context/AuthContext";
import { ThemeProvider } from "@/context/ThemeContext";
import { router } from "@/routes/router";

// Task 3: the full composition. The route-level ErrorBoundary wraps the
// tree; the router table carries the guards (RequireAuth / PublicOnly).
function App() {
  return (
    <ErrorBoundary>
      <ThemeProvider>
        <AuthProvider>
          <RouterProvider router={router} />
        </AuthProvider>
      </ThemeProvider>
    </ErrorBoundary>
  );
}

export default App;
