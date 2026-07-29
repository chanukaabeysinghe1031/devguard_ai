import { Link } from "react-router-dom";

import { BackendStatusBadge } from "../components/BackendStatusBadge";

export function HomePage() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center px-6">
      <div className="w-full max-w-2xl rounded-2xl border border-surface-border bg-surface-elevated p-10 shadow-2xl">
        <div className="mb-6 flex items-center justify-between">
          <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-accent/20 text-xl font-bold text-accent">
            DG
          </div>
          <BackendStatusBadge />
        </div>

        <h1 className="text-4xl font-bold tracking-tight text-white">DevGuard AI</h1>
        <p className="mt-3 text-lg text-slate-400">AI-Powered DevOps Intelligence Platform</p>

        <div className="mt-8 rounded-lg border border-surface-border bg-surface p-4 text-sm text-slate-400">
          Upload a CI/CD failure log, retrieve grounded knowledge, and view diagnosis plus
          recommendations.
        </div>

        <Link
          to="/diagnose"
          className="mt-6 inline-flex rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-muted"
        >
          Open diagnosis pipeline
        </Link>
      </div>
    </main>
  );
}
