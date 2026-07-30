import { ShieldCheck, X } from "lucide-react";
import { NavLink } from "react-router-dom";

import { useAuth } from "../../hooks/useAuth";
import { useUiStore } from "../../stores/uiStore";
import { cn } from "../../utils/cn";
import { ADMIN_NAV, PRIMARY_NAV } from "./navConfig";

export function MobileNav() {
  const { mobileNavOpen, setMobileNavOpen } = useUiStore();
  const { hasAnyRole } = useAuth();
  const canSeeAdmin = hasAnyRole(["organization_owner", "organization_admin"]);

  if (!mobileNavOpen) return null;

  return (
    <div className="fixed inset-0 z-40 lg:hidden">
      <div
        className="absolute inset-0 bg-black/60"
        onClick={() => setMobileNavOpen(false)}
        aria-hidden="true"
      />
      <div className="relative flex h-full w-72 flex-col border-r border-border bg-surface">
        <div className="flex items-center justify-between border-b border-border px-4" style={{ height: "var(--topbar-height)" }}>
          <div className="flex items-center gap-2">
            <div className="flex h-9 w-9 items-center justify-center rounded-md bg-primary text-white">
              <ShieldCheck className="h-5 w-5" />
            </div>
            <span className="text-lg font-bold text-text-primary">DevGuard AI</span>
          </div>
          <button
            type="button"
            onClick={() => setMobileNavOpen(false)}
            aria-label="Close navigation"
            className="rounded-md p-1.5 text-text-muted hover:bg-surface-hover hover:text-text-primary"
          >
            <X className="h-5 w-5" />
          </button>
        </div>
        <nav className="flex-1 space-y-1 overflow-y-auto px-2.5 py-4">
          {PRIMARY_NAV.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={!item.matchPrefix}
              onClick={() => setMobileNavOpen(false)}
              className={({ isActive }) =>
                cn(
                  "flex items-center gap-3 rounded-md px-3 py-2.5 text-sm font-medium transition-colors",
                  isActive
                    ? "bg-primary/15 text-primary"
                    : "text-text-secondary hover:bg-surface-hover hover:text-text-primary",
                )
              }
            >
              <item.icon className="h-5 w-5 shrink-0" />
              <span>{item.label}</span>
            </NavLink>
          ))}
          {canSeeAdmin && (
            <div className="pt-4">
              <p className="px-3 pb-1.5 text-xs font-semibold uppercase tracking-wide text-text-disabled">
                Admin
              </p>
              {ADMIN_NAV.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  onClick={() => setMobileNavOpen(false)}
                  className={({ isActive }) =>
                    cn(
                      "flex items-center gap-3 rounded-md px-3 py-2.5 text-sm font-medium transition-colors",
                      isActive
                        ? "bg-primary/15 text-primary"
                        : "text-text-secondary hover:bg-surface-hover hover:text-text-primary",
                    )
                  }
                >
                  <item.icon className="h-5 w-5 shrink-0" />
                  <span>{item.label}</span>
                </NavLink>
              ))}
            </div>
          )}
        </nav>
      </div>
    </div>
  );
}
