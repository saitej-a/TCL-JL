import { RouterProvider } from "react-router-dom";

import { ErrorBoundary } from "@/components/ErrorBoundary";
import { ToastProvider } from "@/components/Toast";
import { AuthProvider } from "@/context/AuthContext";
import { ThemeProvider } from "@/context/ThemeContext";
import { router } from "@/routes/router";

// Task 3: the full composition. The route-level ErrorBoundary wraps the
// tree; the router table carries the guards (RequireAuth / PublicOnly).
// 9.3 Task 5: ToastProvider wraps the router (providers live OUTSIDE
// RouterProvider — react-router's documented pattern) so every page can raise
// §6.7.1 toasts: UpvotePill's rollback notice, CreatePostPage's rejections.
function App() {
  return (
    <ErrorBoundary>
      <ThemeProvider>
        <AuthProvider>
          <ToastProvider>
            <RouterProvider router={router} />
          </ToastProvider>
        </AuthProvider>
      </ThemeProvider>
    </ErrorBoundary>
  );
}

export default App;
