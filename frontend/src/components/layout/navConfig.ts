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
  Mail,
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

/** Organization administration — owners/admins only (not platform System). */
export const ORGANIZATION_NAV: NavItem[] = [
  { label: "Members", to: "/organization/members", icon: Users },
  { label: "Invitations", to: "/organization/invitations", icon: Mail },
  { label: "Roles", to: "/organization/roles", icon: ShieldCheck },
];

/** Platform / System — visible only to platform_admin. */
export const SYSTEM_NAV: NavItem[] = [
  { label: "System Health", to: "/system/health", icon: Activity },
  { label: "Models", to: "/system/models", icon: FlaskConical, badge: "Deferred" },
  { label: "Audit Log", to: "/system/audit", icon: ShieldCheck, badge: "Deferred" },
  { label: "Evaluation", to: "/system/evaluation", icon: BarChart3, badge: "Deferred" },
];

/** @deprecated Use ORGANIZATION_NAV / SYSTEM_NAV */
export const ADMIN_NAV = ORGANIZATION_NAV;
