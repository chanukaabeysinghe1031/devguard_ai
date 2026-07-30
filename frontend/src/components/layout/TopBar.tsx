import { Menu, Search } from "lucide-react";

import { useUiStore } from "../../stores/uiStore";
import { NotificationMenu } from "./NotificationMenu";
import { UserMenu } from "./UserMenu";

export function TopBar({ title }: { title?: string }) {
  const { setMobileNavOpen } = useUiStore();

  const openSearch = () => {
    window.dispatchEvent(new CustomEvent("devguard:open-search"));
  };

  return (
    <header
      className="sticky top-0 z-20 flex items-center justify-between border-b border-border bg-surface/95 px-4 backdrop-blur sm:px-6"
      style={{ height: "var(--topbar-height)" }}
    >
      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={() => setMobileNavOpen(true)}
          aria-label="Open navigation"
          className="flex h-10 w-10 items-center justify-center rounded-md text-text-secondary hover:bg-surface-hover lg:hidden"
        >
          <Menu className="h-5 w-5" />
        </button>
        {title && <h2 className="text-base font-semibold text-text-primary sm:text-lg">{title}</h2>}
      </div>
      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={openSearch}
          aria-label="Open global search"
          className="hidden h-10 items-center gap-2 rounded-md border border-border-strong bg-surface-interactive px-3 text-sm text-text-muted hover:bg-surface-hover sm:inline-flex"
        >
          <Search className="h-4 w-4" />
          <span>Search</span>
          <kbd className="rounded border border-border-strong px-1.5 py-0.5 text-[10px]">⌘K</kbd>
        </button>
        <button
          type="button"
          onClick={openSearch}
          aria-label="Open global search"
          className="inline-flex h-10 w-10 items-center justify-center rounded-md text-text-secondary hover:bg-surface-hover sm:hidden"
        >
          <Search className="h-5 w-5" />
        </button>
        <NotificationMenu />
        <UserMenu />
      </div>
    </header>
  );
}
