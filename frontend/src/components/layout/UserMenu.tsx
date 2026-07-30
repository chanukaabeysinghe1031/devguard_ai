import { useRef, useState } from "react";
import { ChevronDown, LogOut, Settings, UserRound } from "lucide-react";
import { Link, useNavigate } from "react-router-dom";

import { useAuth } from "../../hooks/useAuth";
import { useClickOutside } from "../../hooks/useClickOutside";
import { Avatar } from "../ui/Avatar";
import { titleCase } from "../../utils/formatters";

export function UserMenu() {
  const { session, user, logout } = useAuth();
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();

  useClickOutside(containerRef, () => setOpen(false), open);

  const displayName = user?.full_name ?? session?.fullName ?? session?.email ?? "Account";
  const roleLabel = titleCase(session?.role ?? undefined);

  const handleLogout = async () => {
    setOpen(false);
    await logout();
    navigate("/login", { replace: true });
  };

  return (
    <div className="relative" ref={containerRef}>
      <button
        type="button"
        onClick={() => setOpen((prev) => !prev)}
        aria-haspopup="menu"
        aria-expanded={open}
        className="flex items-center gap-2 rounded-md px-2 py-1.5 transition-colors hover:bg-surface-hover"
      >
        <Avatar name={displayName} size="sm" />
        <span className="hidden text-left text-sm sm:block">
          <span className="block font-medium leading-none text-text-primary">{displayName}</span>
          {roleLabel && <span className="block text-xs leading-none text-text-muted">{roleLabel}</span>}
        </span>
        <ChevronDown className="h-4 w-4 text-text-muted" />
      </button>

      {open && (
        <div
          role="menu"
          className="absolute right-0 z-40 mt-2 w-56 rounded-md border border-border-strong bg-surface-elevated py-1.5 shadow-elevated"
        >
          <div className="border-b border-border px-3 py-2">
            <p className="truncate text-sm font-medium text-text-primary">{displayName}</p>
            <p className="truncate text-xs text-text-muted">{session?.email}</p>
          </div>
          <Link
            to="/profile"
            role="menuitem"
            onClick={() => setOpen(false)}
            className="flex items-center gap-2 px-3 py-2 text-sm text-text-secondary hover:bg-surface-hover hover:text-text-primary"
          >
            <UserRound className="h-4 w-4" /> Profile
          </Link>
          <Link
            to="/settings"
            role="menuitem"
            onClick={() => setOpen(false)}
            className="flex items-center gap-2 px-3 py-2 text-sm text-text-secondary hover:bg-surface-hover hover:text-text-primary"
          >
            <Settings className="h-4 w-4" /> Settings
          </Link>
          <button
            type="button"
            role="menuitem"
            onClick={handleLogout}
            className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-danger hover:bg-danger/10"
          >
            <LogOut className="h-4 w-4" /> Sign out
          </button>
        </div>
      )}
    </div>
  );
}
