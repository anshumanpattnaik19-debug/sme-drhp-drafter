import { Component, type ErrorInfo, type ReactNode } from "react";
import { AlertTriangle } from "lucide-react";
import { Button } from "./ui";

interface State {
  error: Error | null;
}

/**
 * Last line of defence: an unexpected render error shows a recoverable message
 * instead of a blank page. The technical detail is kept in the console.
 */
export class ErrorBoundary extends Component<{ children: ReactNode }, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("UI error", error, info.componentStack);
  }

  render() {
    if (!this.state.error) return this.props.children;
    return (
      <div role="alert" className="flex h-full items-center justify-center p-8">
        <div className="max-w-md text-center">
          <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-xl bg-danger-soft text-danger">
            <AlertTriangle className="h-6 w-6" />
          </div>
          <h1 className="mt-4 text-lg font-semibold text-fg">Something went wrong on this page</h1>
          <p className="mt-2 text-[13px] leading-relaxed text-fg-muted">
            Your project data is saved on this machine. Reload the page to continue; if the problem
            returns, check the browser console and the service log.
          </p>
          <div className="mt-6 flex justify-center gap-2">
            <Button variant="secondary" onClick={() => this.setState({ error: null })}>Try again</Button>
            <Button variant="primary" onClick={() => window.location.reload()}>Reload</Button>
          </div>
        </div>
      </div>
    );
  }
}
