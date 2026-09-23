import { Component, type ErrorInfo, type ReactNode } from "react";

/**
 * The route-level Error Boundary (Task 3). 11 §4.2's copy VERBATIM:
 * "Something went wrong." + a "Reload Application" button. Raw error details
 * go to the console (the single logging place) and are never rendered to the
 * user.
 */
interface ErrorBoundaryProps {
  children: ReactNode;
}

interface ErrorBoundaryState {
  hasError: boolean;
}

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  state: ErrorBoundaryState = { hasError: false };

  static getDerivedStateFromError(): ErrorBoundaryState {
    return { hasError: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    // One logging place — no raw error surfaces in the UI.
    console.error("[ErrorBoundary]", error, info.componentStack);
  }

  private handleReload = (): void => {
    window.location.reload();
  };

  render(): ReactNode {
    if (this.state.hasError) {
      return (
        <div
          role="alert"
          className="min-h-screen flex flex-col items-center justify-center gap-4 p-8 text-center"
        >
          <h1 className="text-2xl font-bold">Something went wrong.</h1>
          <p className="text-sm text-slate-500 dark:text-slate-400">
            An unexpected error occurred. Reloading the application usually resolves it.
          </p>
          <button
            type="button"
            onClick={this.handleReload}
            className="bg-brand-600 hover:bg-brand-700 active:bg-brand-800 text-white font-medium rounded-lg shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 transition-colors h-10 px-4 text-sm"
          >
            Reload Application
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}
