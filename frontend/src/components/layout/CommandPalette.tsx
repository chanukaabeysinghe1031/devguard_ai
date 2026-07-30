import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { FileText, FolderKanban, Search } from "lucide-react";

import { listIncidents } from "../../api/incidentsApi";
import { listProjects } from "../../api/projectsApi";
import { cn } from "../../utils/cn";

type ResultItem = {
  id: string;
  label: string;
  meta: string;
  href: string;
  group: "Projects" | "Incidents";
};

export function CommandPalette() {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState<ResultItem[]>([]);
  const [activeIndex, setActiveIndex] = useState(0);
  const navigate = useNavigate();

  const close = useCallback(() => {
    setOpen(false);
    setQuery("");
    setResults([]);
    setActiveIndex(0);
  }, []);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setOpen((prev) => !prev);
      }
      if (event.key === "Escape" && open) {
        event.preventDefault();
        close();
      }
    };
    const onOpen = () => setOpen(true);
    window.addEventListener("keydown", onKey);
    window.addEventListener("devguard:open-search", onOpen);
    return () => {
      window.removeEventListener("keydown", onKey);
      window.removeEventListener("devguard:open-search", onOpen);
    };
  }, [close, open]);

  useEffect(() => {
    if (!open) return;
    const q = query.trim();
    if (q.length < 2) {
      setResults([]);
      return;
    }
    let cancelled = false;
    const timer = window.setTimeout(async () => {
      setLoading(true);
      try {
        const [projects, incidents] = await Promise.all([
          listProjects({ page: 1, page_size: 8, search: q }),
          listIncidents({ page: 1, page_size: 8, search: q }),
        ]);
        if (cancelled) return;
        const next: ResultItem[] = [
          ...projects.items.map((p) => ({
            id: `p-${p.id}`,
            label: p.name,
            meta: p.key,
            href: `/projects/${p.id}`,
            group: "Projects" as const,
          })),
          ...incidents.items.map((i) => ({
            id: `i-${i.id}`,
            label: i.title,
            meta: `${i.incident_number} · ${i.project.name}`,
            href: `/incidents/${i.id}`,
            group: "Incidents" as const,
          })),
        ];
        setResults(next);
        setActiveIndex(0);
      } catch {
        if (!cancelled) setResults([]);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }, 250);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [open, query]);

  const grouped = useMemo(() => {
    const map = new Map<string, ResultItem[]>();
    for (const item of results) {
      const list = map.get(item.group) ?? [];
      list.push(item);
      map.set(item.group, list);
    }
    return map;
  }, [results]);

  const flat = results;

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-[60] flex items-start justify-center bg-black/60 p-4 pt-[12vh]"
      role="presentation"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) close();
      }}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Global search"
        className="w-full max-w-xl overflow-hidden rounded-xl border border-border-strong bg-surface-elevated shadow-elevated"
      >
        <div className="flex items-center gap-2 border-b border-border px-3">
          <Search className="h-4 w-4 text-text-muted" aria-hidden />
          <input
            autoFocus
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search projects and incidents…"
            aria-label="Search projects and incidents"
            className="h-12 w-full bg-transparent text-sm text-text-primary placeholder:text-text-disabled focus:outline-none"
            onKeyDown={(e) => {
              if (e.key === "ArrowDown") {
                e.preventDefault();
                setActiveIndex((i) => Math.min(i + 1, Math.max(flat.length - 1, 0)));
              } else if (e.key === "ArrowUp") {
                e.preventDefault();
                setActiveIndex((i) => Math.max(i - 1, 0));
              } else if (e.key === "Enter" && flat[activeIndex]) {
                e.preventDefault();
                navigate(flat[activeIndex].href);
                close();
              }
            }}
          />
          <kbd className="hidden rounded border border-border-strong px-1.5 py-0.5 text-[10px] text-text-muted sm:inline">
            Esc
          </kbd>
        </div>
        <div className="max-h-80 overflow-y-auto p-2" role="listbox">
          {loading && <p className="px-3 py-4 text-sm text-text-muted">Searching…</p>}
          {!loading && query.trim().length >= 2 && flat.length === 0 && (
            <p className="px-3 py-4 text-sm text-text-muted">No matching projects or incidents.</p>
          )}
          {!loading && query.trim().length < 2 && (
            <p className="px-3 py-4 text-sm text-text-muted">Type at least two characters. Results come from live APIs.</p>
          )}
          {[...grouped.entries()].map(([group, items]) => (
            <div key={group} className="mb-2">
              <p className="px-2 py-1 text-[11px] font-semibold uppercase tracking-wide text-text-disabled">
                {group}
              </p>
              {items.map((item) => {
                const index = flat.findIndex((r) => r.id === item.id);
                const Icon = item.group === "Projects" ? FolderKanban : FileText;
                return (
                  <button
                    key={item.id}
                    type="button"
                    role="option"
                    aria-selected={index === activeIndex}
                    className={cn(
                      "flex w-full items-center gap-3 rounded-md px-3 py-2 text-left text-sm",
                      index === activeIndex
                        ? "bg-primary/15 text-primary"
                        : "text-text-secondary hover:bg-surface-hover",
                    )}
                    onMouseEnter={() => setActiveIndex(index)}
                    onClick={() => {
                      navigate(item.href);
                      close();
                    }}
                  >
                    <Icon className="h-4 w-4 shrink-0" />
                    <span className="min-w-0 flex-1">
                      <span className="block truncate font-medium text-text-primary">{item.label}</span>
                      <span className="block truncate text-xs text-text-muted">{item.meta}</span>
                    </span>
                  </button>
                );
              })}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
