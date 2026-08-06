import { cn } from "@/lib/utils";

export function PageHeader({
  eyebrow,
  title,
  description,
  className,
  actions,
}: {
  eyebrow?: string;
  title: string;
  description?: string;
  className?: string;
  actions?: React.ReactNode;
}) {
  return (
    <div className={cn("mb-7 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between", className)}>
      <div>
        {eyebrow && (
          <p className="mb-1.5 font-mono text-[11px] font-medium uppercase tracking-[0.1em] text-accent">{eyebrow}</p>
        )}
        <h1 className="text-2xl font-semibold tracking-tight text-ink text-balance">{title}</h1>
        {description && <p className="mt-1.5 max-w-[68ch] text-sm leading-relaxed text-ink-dim">{description}</p>}
      </div>
      {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
    </div>
  );
}
