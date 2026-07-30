import { ShieldCheck } from "lucide-react";
import { Outlet } from "react-router-dom";

export function AuthLayout() {
  return (
    <div className="grid min-h-screen grid-cols-1 bg-background lg:grid-cols-2">
      <div className="flex flex-col justify-center px-6 py-12 sm:px-12 lg:px-16">
        <div className="mx-auto w-full max-w-sm">
          <div className="mb-8 flex items-center gap-2.5">
            <div className="flex h-10 w-10 items-center justify-center rounded-md bg-primary text-white">
              <ShieldCheck className="h-6 w-6" />
            </div>
            <span className="text-xl font-bold text-text-primary">DevGuard AI</span>
          </div>
          <Outlet />
        </div>
      </div>

      <div className="relative hidden overflow-hidden bg-surface lg:flex lg:flex-col lg:items-center lg:justify-center">
        <div
          className="absolute inset-0 opacity-40"
          style={{
            backgroundImage:
              "radial-gradient(circle at 20% 20%, rgba(37, 99, 235, 0.35), transparent 45%), radial-gradient(circle at 80% 70%, rgba(124, 58, 237, 0.3), transparent 45%)",
          }}
        />
        <div className="relative z-10 max-w-md px-10 text-center">
          <h2 className="text-2xl font-bold text-text-primary">
            AI-powered DevOps incident intelligence
          </h2>
          <p className="mt-4 text-sm leading-relaxed text-text-secondary">
            Classify CI/CD failures, extract grounded evidence, and get explainable root-cause
            reasoning with confidence-aware recommendations — end to end, in one incident workspace.
          </p>
        </div>
      </div>
    </div>
  );
}
