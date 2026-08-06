import { cn } from "@/lib/utils";
import type { KpiItem } from "@/types/report";
import { Reveal } from "./reveal";
import type { LucideIcon } from "lucide-react";

export function KpiCard({ item, icon: Icon, index = 0 }: { item: KpiItem; icon?: LucideIcon; index?: number }) {
  return (
    <Reveal index={index}>
      <div className="group relative overflow-hidden rounded-[var(--radius)] border border-border bg-bg-elevated p-4 shadow-[var(--shadow-sm)] transition-shadow hover:shadow-[var(--shadow-md)]">
        <div className="flex items-start justify-between gap-2">
          <p className="text-[11px] font-medium uppercase tracking-[0.06em] text-ink-faint">{item.label}</p>
          {Icon && <Icon className="h-3.5 w-3.5 text-ink-faint" strokeWidth={1.75} />}
        </div>
        <p className={cn("mt-2 truncate font-mono text-[22px] font-semibold leading-none text-ink tabular-nums")}>
          {item.value}
        </p>
        {item.sub && <p className="mt-1.5 truncate text-[12px] text-ink-dim">{item.sub}</p>}
        <div className="absolute inset-x-0 bottom-0 h-0.5 origin-left scale-x-0 bg-accent transition-transform duration-300 group-hover:scale-x-100" />
      </div>
    </Reveal>
  );
}
