import { useState, type ReactNode } from "react";

import { cn } from "../../utils/cn";

export function Tooltip({
  content,
  children,
  side = "top",
  className,
}: {
  content: ReactNode;
  children: ReactNode;
  side?: "top" | "bottom" | "left" | "right";
  className?: string;
}) {
  const [visible, setVisible] = useState(false);

  const positionClasses: Record<typeof side, string> = {
    top: "bottom-full left-1/2 mb-2 -translate-x-1/2",
    bottom: "top-full left-1/2 mt-2 -translate-x-1/2",
    left: "right-full top-1/2 mr-2 -translate-y-1/2",
    right: "left-full top-1/2 ml-2 -translate-y-1/2",
  };

  return (
    <span
      className="relative inline-flex"
      onMouseEnter={() => setVisible(true)}
      onMouseLeave={() => setVisible(false)}
      onFocus={() => setVisible(true)}
      onBlur={() => setVisible(false)}
    >
      {children}
      {visible && (
        <span
          role="tooltip"
          className={cn(
            "pointer-events-none absolute z-50 max-w-xs whitespace-normal rounded-md border border-border-strong bg-surface-elevated px-2.5 py-1.5 text-xs text-text-primary shadow-elevated",
            positionClasses[side],
            className,
          )}
        >
          {content}
        </span>
      )}
    </span>
  );
}
