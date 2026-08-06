import { Badge } from "@/components/ui/badge";
import type { Severity } from "@/types/report";
import { cn } from "@/lib/utils";

const meta: Record<Severity, { tone: "crit" | "warn" | "info" | "neutral"; label: string }> = {
  critical: { tone: "crit", label: "Critical" },
  high: { tone: "crit", label: "High" },
  medium: { tone: "warn", label: "Medium" },
  low: { tone: "info", label: "Low" },
};

export function SeverityBadge({ severity, className }: { severity: Severity; className?: string }) {
  const m = meta[severity];
  return (
    <Badge tone={m.tone} className={cn(className)}>
      {m.label}
    </Badge>
  );
}
