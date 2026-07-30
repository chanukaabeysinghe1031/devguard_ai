import { ChevronsLeft, ChevronsRight, ShieldCheck } from "lucide-react";
import { NavLink } from "react-router-dom";

import { cn } from "../../utils/cn";
import { useAuth } from "../../hooks/useAuth";
import { useUiStore } from "../../stores/uiStore";
import { Tooltip } from "../ui/Tooltip";
import { ADMIN_NAV, PRIMARY_NAV, type NavItem } from "./navConfig";

function NavRow({ item, collapsed }: { item: NavItem; collapsed: boolean }) {
  const content = (
    <NavLink
      to={item.to}
      end={!item.matchPrefix}
      className={({ isActive }) =>
        cn(
          "flex items-center gap-3 rounded-md px-3 py-2.5 text-sm font-medium transition-colors",
          isActive
            ? "bg-primary/15 text-primary"
            : "text-text-secondary hover:bg-surface-hover hover:text-text-primary",
          collapsed && "justify-center px-2",
        )
      }
    >
      <item.icon className="h-5 w-5 shrink-0" />
      {!collapsed && (
        <span className="flex min-w-0 flex-1 items-center justify-between gap-2">
          <span className="truncate">{item.label}</span>
          {item.badge && (
            <span className="shrink-0 rounded-full border border-border-strong px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-text-muted">
              {item.badge}
            </span>
          )}
        </span>
      )}
    </NavLink>
  );

  if (collapsed) {
    return (
      <Tooltip content={item.badge ? `${item.label} (${item.badge})` : item.label} side="right">
        {content}
      </Tooltip>
    );
  }
  return content;
}

export function Sidebar() {
  const { sidebarCollapsed, toggleSidebar } = useUiStore();
  const { hasAnyRole } = useAuth();
  const canSeeAdmin = hasAnyRole(["organization_owner", "organization_admin"]);

  return (
    <aside
      className={cn(
        "fixed inset-y-0 left-0 z-30 hidden flex-col border-r border-border bg-surface transition-[width] duration-200 lg:flex",
      )}
      style={{ width: sidebarCollapsed ? "var(--sidebar-collapsed)" : "var(--sidebar-expanded)" }}
      aria-label="Primary navigation"
    >
      <div
        className={cn(
          "flex items-center gap-2 border-b border-border px-4",
          sidebarCollapsed && "justify-center px-0",
        )}
        style={{ height: "var(--topbar-height)" }}
      >
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-primary text-white">
          <ShieldCheck className="h-5 w-5" />
        </div>
        {!sidebarCollapsed && <span className="text-lg font-bold text-text-primary">DevGuard AI</span>}
      </div>

      <nav className="flex-1 space-y-1 overflow-y-auto px-2.5 py-4">
        {PRIMARY_NAV.map((item) => (
          <NavRow key={item.to} item={item} collapsed={sidebarCollapsed} />
        ))}

        {canSeeAdmin && (
          <div className="pt-4">
            {!sidebarCollapsed && (
              <p className="px-3 pb-1.5 text-xs font-semibold uppercase tracking-wide text-text-disabled">
                Admin
              </p>
            )}
            {ADMIN_NAV.map((item) => (
              <NavRow key={item.to} item={item} collapsed={sidebarCollapsed} />
            ))}
          </div>
        )}
      </nav>

      <div className="border-t border-border p-2.5">
        <button
          type="button"
          onClick={toggleSidebar}
          className="flex w-full items-center justify-center gap-2 rounded-md px-3 py-2 text-sm text-text-muted transition-colors hover:bg-surface-hover hover:text-text-primary"
          aria-label={sidebarCollapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          {sidebarCollapsed ? <ChevronsRight className="h-4 w-4" /> : <ChevronsLeft className="h-4 w-4" />}
          {!sidebarCollapsed && <span>Collapse</span>}
        </button>
      </div>
    </aside>
  );
}
