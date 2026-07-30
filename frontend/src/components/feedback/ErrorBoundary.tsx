import { Component, type ErrorInfo, type ReactNode } from "react";
import { Link } from "react-router-dom";

import { Button } from "../ui/Button";
import { Card, CardBody } from "../ui/Card";

type Props = { children: ReactNode };
type State = { hasError: boolean; message: string };

export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false, message: "" };

  static getDerivedStateFromError(error: Error): State {
    return {
      hasError: true,
      message: error.message || "An unexpected error occurred.",
    };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    // Never log tokens/secrets; message only for diagnostics.
    console.error("UI error boundary caught:", error.message, info.componentStack);
  }

  private reset = () => {
    this.setState({ hasError: false, message: "" });
  };

  render() {
    if (!this.state.hasError) return this.props.children;

    return (
      <div className="flex min-h-[50vh] items-center justify-center p-6" role="alert">
        <Card className="max-w-lg w-full">
          <CardBody>
            <h1 className="text-xl font-semibold text-text-primary">Something went wrong</h1>
            <p className="mt-2 text-sm text-text-secondary">
              The page failed to render. You can retry or return to the dashboard. Technical details are
              not shown to protect sensitive context.
            </p>
            {import.meta.env.DEV && this.state.message && (
              <p className="mt-3 rounded-md border border-border bg-surface-interactive p-3 font-mono text-xs text-text-muted">
                {this.state.message}
              </p>
            )}
            <div className="mt-4 flex flex-wrap gap-2">
              <Button type="button" onClick={this.reset}>
                Try again
              </Button>
              <Link
                to="/dashboard"
                className="inline-flex h-11 items-center rounded-md border border-border-strong px-4 text-sm font-medium text-text-secondary hover:bg-surface-hover"
                onClick={this.reset}
              >
                Go to dashboard
              </Link>
            </div>
          </CardBody>
        </Card>
      </div>
    );
  }
}
