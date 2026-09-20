import type { ReactNode } from "react";
export type StatItem = { label: string; value: ReactNode; subline?: ReactNode };
export function StatStrip({ items }: { items: StatItem[] }) {
  return (
    <div className="stats">
      {items.map((item) => (
        <div className="stat" key={item.label}>
          <div className="stat-value">{item.value}</div>
          <div className="stat-label">{item.label}</div>
          {item.subline && <div className="stat-subline">{item.subline}</div>}
        </div>
      ))}
    </div>
  );
}
