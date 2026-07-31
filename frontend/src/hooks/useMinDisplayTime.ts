import { useEffect, useState } from "react";

/** Ensures a loader remains visible briefly to avoid a flash, without blocking forever. */
export function useMinDisplayTime(active: boolean, minMs = 700): boolean {
  const [elapsed, setElapsed] = useState(!active);

  useEffect(() => {
    if (!active) {
      setElapsed(true);
      return;
    }
    setElapsed(false);
    const timer = window.setTimeout(() => setElapsed(true), minMs);
    return () => window.clearTimeout(timer);
  }, [active, minMs]);

  return elapsed;
}
