import { cn } from "../utils/cn";

const NODES = [
  { top: "18%", left: "22%", delay: "0s" },
  { top: "28%", left: "78%", delay: "0.6s" },
  { top: "62%", left: "16%", delay: "1.1s" },
  { top: "70%", left: "72%", delay: "1.7s" },
  { top: "46%", left: "48%", delay: "2.2s" },
] as const;

/**
 * Ambient visual panel for authentication screens.
 * No brand image here — the splash page and form header own the logo.
 */
export function AuthVisualPanel({ className }: { className?: string }) {
  return (
    <div
      className={cn(
        "relative hidden overflow-hidden bg-surface lg:flex lg:flex-col lg:items-center lg:justify-center",
        className,
      )}
      aria-hidden
    >
      <div
        className="brand-auth-ambient absolute inset-0 opacity-70"
        style={{
          backgroundImage:
            "radial-gradient(circle at 20% 20%, rgba(37, 99, 235, 0.4), transparent 45%), radial-gradient(circle at 80% 70%, rgba(124, 58, 237, 0.35), transparent 45%), radial-gradient(circle at 50% 50%, rgba(6, 182, 212, 0.12), transparent 55%)",
        }}
      />

      <div
        className="absolute inset-0 opacity-[0.12]"
        style={{
          backgroundImage:
            "linear-gradient(rgba(148,163,184,0.35) 1px, transparent 1px), linear-gradient(90deg, rgba(148,163,184,0.35) 1px, transparent 1px)",
          backgroundSize: "48px 48px",
          maskImage: "radial-gradient(circle at center, black 30%, transparent 75%)",
        }}
      />

      {NODES.map((node) => (
        <span
          key={`${node.top}-${node.left}`}
          className="brand-circuit-node absolute h-2 w-2 rounded-full bg-info shadow-[0_0_12px_rgba(6,182,212,0.8)]"
          style={{ top: node.top, left: node.left, animationDelay: node.delay }}
        />
      ))}

      <div className="relative z-10 max-w-md px-10 text-center">
        <h2 className="text-2xl font-bold text-text-primary">AI-powered incident intelligence</h2>
        <p className="mt-4 text-sm leading-relaxed text-text-secondary">
          Classify CI/CD failures, extract grounded evidence, and get explainable root-cause
          reasoning with confidence-aware recommendations — in one incident workspace.
        </p>
      </div>
    </div>
  );
}
