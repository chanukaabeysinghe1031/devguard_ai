import { useEffect, useState } from "react";

import { BackendStatus, fetchBackendHealth } from "../api/health";

export function BackendStatusBadge() {
  const [status, setStatus] = useState<BackendStatus>("loading");

  useEffect(() => {
    let cancelled = false;

    async function checkHealth() {
      try {
        await fetchBackendHealth();
        if (!cancelled) {
          setStatus("online");
        }
      } catch {
        if (!cancelled) {
          setStatus("offline");
        }
      }
    }

    void checkHealth();
    return () => {
      cancelled = true;
    };
  }, []);

  const label =
    status === "loading" ? "Loading" : status === "online" ? "Backend Online" : "Backend Offline";

  const colorClass =
    status === "loading"
      ? "bg-slate-700 text-slate-200"
      : status === "online"
        ? "bg-emerald-900/60 text-emerald-300 border-emerald-700"
        : "bg-red-900/60 text-red-300 border-red-700";

  return (
    <span
      className={`inline-flex items-center rounded-full border px-4 py-1.5 text-sm font-medium ${colorClass}`}
    >
      {status === "loading" && (
        <span className="mr-2 inline-block h-2 w-2 animate-pulse rounded-full bg-slate-300" />
      )}
      {label}
    </span>
  );
}
