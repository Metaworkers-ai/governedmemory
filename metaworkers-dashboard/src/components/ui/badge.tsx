import * as React from "react";
import { cn } from "@/lib/utils";
import type { Status } from "@/types/report";

const toneClasses: Record<string, string> = {
  good: "bg-good-bg text-good border-good-border",
  warn: "bg-warn-bg text-warn border-warn-border",
  crit: "bg-crit-bg text-crit border-crit-border",
  info: "bg-info-bg text-info border-info-border",
  neutral: "bg-accent-soft text-accent border-accent/20",
  outline: "bg-transparent text-ink-dim border-border",
};

export function Badge({
  className,
  tone = "neutral",
  children,
  ...props
}: React.HTMLAttributes<HTMLSpanElement> & { tone?: keyof typeof toneClasses }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-[11px] font-medium font-mono tracking-wide whitespace-nowrap",
        toneClasses[tone],
        className
      )}
      {...props}
    >
      {children}
    </span>
  );
}

export function StatusBadge({ status }: { status: Status }) {
  const map: Record<Status, { tone: keyof typeof toneClasses; label: string }> = {
    working: { tone: "good", label: "Working" },
    partial: { tone: "warn", label: "Partial" },
    missing: { tone: "crit", label: "Missing" },
  };
  const m = map[status];
  return (
    <Badge tone={m.tone}>
      <span className={cn("h-1.5 w-1.5 rounded-full", m.tone === "good" ? "bg-good" : m.tone === "warn" ? "bg-warn" : "bg-crit")} />
      {m.label}
    </Badge>
  );
}
