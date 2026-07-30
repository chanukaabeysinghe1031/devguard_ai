import type { ReactNode } from "react";

export interface KeyValueItem {
  label: string;
  value: ReactNode;
}

export function KeyValueList({ items, columns = 1 }: { items: KeyValueItem[]; columns?: 1 | 2 }) {
  return (
    <dl className={columns === 2 ? "grid grid-cols-1 gap-x-6 gap-y-3 sm:grid-cols-2" : "flex flex-col gap-3"}>
      {items.map((item) => (
        <div key={item.label} className="flex flex-col gap-0.5">
          <dt className="text-xs font-medium uppercase tracking-wide text-text-muted">{item.label}</dt>
          <dd className="text-sm text-text-primary">{item.value}</dd>
        </div>
      ))}
    </dl>
  );
}
