import { Outlet } from "react-router-dom";

import { BrandMark } from "../components/brand/BrandMark";
import { AuthVisualPanel } from "./AuthVisualPanel";

export function AuthLayout() {
  return (
    <div className="grid min-h-screen grid-cols-1 bg-background lg:grid-cols-2">
      <div className="flex flex-col justify-center px-6 py-10 sm:px-12 lg:px-16">
        <div className="brand-form-enter mx-auto w-full max-w-sm">
          <div className="mb-8 flex items-center justify-center gap-4 sm:justify-start">
            <BrandMark size="xl" framed={false} priority />
            <div className="min-w-0 text-left">
              <p className="text-2xl font-bold leading-tight tracking-tight text-text-primary">
                DevGuard{" "}
                <span className="bg-gradient-to-r from-info via-primary to-secondary bg-clip-text text-transparent">
                  AI
                </span>
              </p>
              <p className="mt-1 text-[11px] font-semibold uppercase tracking-[0.16em] text-text-muted">
                AI-Powered Incident Intelligence
              </p>
            </div>
          </div>
          <Outlet />
        </div>
      </div>

      <AuthVisualPanel />
    </div>
  );
}
