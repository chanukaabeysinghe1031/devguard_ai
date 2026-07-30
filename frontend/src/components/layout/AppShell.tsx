import { useEffect } from "react";
import { Outlet } from "react-router-dom";

import { ErrorBoundary } from "../feedback/ErrorBoundary";
import { useUiStore } from "../../stores/uiStore";
import { CommandPalette } from "./CommandPalette";
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
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-[100] focus:rounded-md focus:bg-primary focus:px-4 focus:py-2 focus:text-sm focus:font-medium focus:text-white"
      >
        Skip to content
      </a>
      <Sidebar />
      <MobileNav />
      <CommandPalette />
      <div className="flex min-h-screen flex-col lg:ml-[var(--content-margin)]">
        <TopBar />
        <main id="main-content" tabIndex={-1} className="flex-1 px-4 py-6 sm:px-6 lg:px-8">
          <div className="mx-auto w-full max-w-content">
            <ErrorBoundary>
              <Outlet />
            </ErrorBoundary>
          </div>
        </main>
      </div>
    </div>
  );
}
