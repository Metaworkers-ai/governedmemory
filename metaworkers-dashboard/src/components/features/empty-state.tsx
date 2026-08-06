import type { LucideIcon } from "lucide-react";

export function EmptyState({ icon: Icon, title, description }: { icon: LucideIcon; title: string; description: string }) {
  return (
    <div className="flex flex-col items-center justify-center rounded-[var(--radius)] border border-dashed border-border bg-bg-sunken px-6 py-14 text-center">
      <div className="mb-3 flex h-11 w-11 items-center justify-center rounded-full bg-bg-elevated text-ink-faint">
        <Icon className="h-5 w-5" strokeWidth={1.5} />
      </div>
      <p className="text-[14px] font-medium text-ink">{title}</p>
      <p className="mt-1 max-w-sm text-[13px] text-ink-dim">{description}</p>
    </div>
  );
}
