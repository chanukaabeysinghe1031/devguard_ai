import { AlertTriangle } from "lucide-react";
import { Link } from "react-router-dom";

import { Button } from "../../components/ui/Button";
import { Card, CardBody } from "../../components/ui/Card";

/** Recoverable error page for unexpected navigation/runtime failures. */
export function ErrorPage() {
  return (
    <div className="flex min-h-[60vh] items-center justify-center p-6">
      <Card className="w-full max-w-lg">
        <CardBody>
          <div className="flex items-start gap-3">
            <AlertTriangle className="mt-0.5 h-5 w-5 text-warning" aria-hidden />
            <div>
              <h1 className="text-xl font-semibold text-text-primary">Recoverable error</h1>
              <p className="mt-2 text-sm text-text-secondary">
                Something went wrong while loading this view. You can reload the dashboard or sign in
                again. Stack traces are never shown in production.
              </p>
              <div className="mt-4 flex flex-wrap gap-2">
                <Button type="button" onClick={() => window.location.assign("/dashboard")}>
                  Reload dashboard
                </Button>
                <Link
                  to="/login"
                  className="inline-flex h-11 items-center rounded-md border border-border-strong px-4 text-sm font-medium text-text-secondary hover:bg-surface-hover"
                >
                  Sign in again
                </Link>
              </div>
            </div>
          </div>
        </CardBody>
      </Card>
    </div>
  );
}
