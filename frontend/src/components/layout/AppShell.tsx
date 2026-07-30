import { useEffect } from "react";
import { Outlet } from "react-router-dom";

import { useUiStore } from "../../stores/uiStore";
import { MobileNav } from "./MobileNav";
import { Sidebar } from "./Sidebar";
import { TopBar } from "./TopBar";

export function AppShell() {
  const { sidebarCollapsed } = useUiStore();

  useEffect(() => {
    document.documentElement.style.setProperty(
      "--content-margin",
      sidebarCollapsed ? "var(--sidebar-collapsed)" : "var(--sidebar-expanded)",
    );
  }, [sidebarCollapsed]);

  return (
    <div className="min-h-screen bg-background">
      <Sidebar />
      <MobileNav />
      <div className="flex min-h-screen flex-col lg:ml-[var(--content-margin)]">
        <TopBar />
        <main className="flex-1 px-4 py-6 sm:px-6 lg:px-8">
          <div className="mx-auto w-full max-w-content">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
}
