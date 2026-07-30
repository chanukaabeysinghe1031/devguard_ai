import { useState } from "react";
import { Check, Copy } from "lucide-react";

import { cn } from "../../utils/cn";

export function CodeBlock({
  code,
  language,
  className,
  maxHeight = "24rem",
}: {
  code: string;
  language?: string;
  className?: string;
  maxHeight?: string;
}) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      setCopied(false);
    }
  };

  return (
    <div className={cn("relative overflow-hidden rounded-md border border-border bg-[#0a0f1a]", className)}>
      <div className="flex items-center justify-between border-b border-border px-3 py-1.5">
        <span className="text-xs uppercase tracking-wide text-text-muted">{language ?? "text"}</span>
        <button
          type="button"
          onClick={handleCopy}
          className="flex items-center gap-1 rounded px-2 py-1 text-xs text-text-muted transition-colors hover:bg-surface-hover hover:text-text-primary"
        >
          {copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
          {copied ? "Copied" : "Copy"}
        </button>
      </div>
      <pre className="overflow-auto p-3 text-xs leading-relaxed text-text-secondary" style={{ maxHeight }}>
        <code>{code}</code>
      </pre>
    </div>
  );
}
