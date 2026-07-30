import type { LucideIcon } from "lucide-react";
import {
  Activity,
  BarChart3,
  Bell,
  FileText,
  FlaskConical,
  FolderKanban,
  History,
  LayoutDashboard,
  Settings,
  ShieldCheck,
  Users,
} from "lucide-react";

export interface NavItem {
  label: string;
  to: string;
  icon: LucideIcon;
  matchPrefix?: boolean;
  /** Shown in nav when the destination is intentionally deferred. */
  badge?: string;
}

export const PRIMARY_NAV: NavItem[] = [
  { label: "Dashboard", to: "/dashboard", icon: LayoutDashboard },
  { label: "Projects", to: "/projects", icon: FolderKanban, matchPrefix: true },
  { label: "Incidents", to: "/incidents", icon: Activity, matchPrefix: true },
  { label: "History", to: "/history", icon: History },
  { label: "Reports", to: "/reports", icon: FileText, matchPrefix: true },
  { label: "Notifications", to: "/notifications", icon: Bell },
  { label: "Evaluation", to: "/evaluation", icon: BarChart3 },
  { label: "Settings", to: "/settings", icon: Settings, matchPrefix: true },
];

export const ADMIN_NAV: NavItem[] = [
  { label: "Users", to: "/admin/users", icon: Users },
  { label: "Models", to: "/admin/models", icon: FlaskConical, badge: "Deferred" },
  { label: "System Health", to: "/admin/system-health", icon: Activity },
  { label: "Audit Log", to: "/admin/audit", icon: ShieldCheck, badge: "Deferred" },
  { label: "Evaluation", to: "/admin/evaluation", icon: BarChart3, badge: "Deferred" },
];
