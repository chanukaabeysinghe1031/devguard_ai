import { NavLink, Outlet } from "react-router-dom";

import { PageHeader } from "../../components/ui/PageHeader";
import { cn } from "../../utils/cn";

const SETTINGS_NAV = [
  { to: "/settings/organization", label: "Organization" },
  { to: "/settings/security", label: "Security" },
  { to: "/settings/notifications", label: "Notification preferences" },
];

export function SettingsLayout() {
  return (
    <div>
      <PageHeader title="Settings" description="Manage your organization, security, and notification preferences." />
      <div className="flex flex-col gap-6 lg:flex-row">
        <nav className="flex shrink-0 flex-row gap-1 overflow-x-auto lg:w-56 lg:flex-col">
          {SETTINGS_NAV.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                cn(
                  "rounded-md px-3 py-2 text-sm font-medium transition-colors",
                  isActive
                    ? "bg-primary/15 text-primary"
                    : "text-text-secondary hover:bg-surface-hover hover:text-text-primary",
                )
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
        <div className="min-w-0 flex-1">
          <Outlet />
        </div>
      </div>
    </div>
  );
}
