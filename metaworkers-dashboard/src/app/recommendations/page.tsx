import { PageHeader } from "@/components/features/page-header";
import { Reveal } from "@/components/features/reveal";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { recommendations } from "@/data/report";
import { cn } from "@/lib/utils";

const priorityTone: Record<string, "crit" | "warn" | "info"> = { high: "crit", medium: "warn", low: "info" };
const progressWidth: Record<string, string> = { "not started": "4%", "in progress": "50%", done: "100%" };

export default function RecommendationsPage() {
  return (
    <div>
      <PageHeader
        eyebrow="16 · Recommendations"
        title={`${recommendations.length} actionable items`}
        description="Ranked by priority. Each maps to a concrete file-level fix, not a vague suggestion."
      />

      <div className="flex flex-col gap-3">
        {recommendations.map((r, i) => (
          <Reveal index={i} key={r.id}>
            <Card>
              <CardContent className="p-4">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge tone={priorityTone[r.priority]}>{r.priority} priority</Badge>
                  <Badge tone="outline">{r.category}</Badge>
                  <span className="ml-auto font-mono text-[11px] text-ink-faint">{r.id}</span>
                </div>
                <p className="mt-2.5 text-[14px] font-semibold text-ink">{r.title}</p>
                <p className="mt-1 text-[12.5px] leading-relaxed text-ink-dim">
                  <span className="font-medium text-ink">Impact — </span>
                  {r.impact}
                </p>
                <p className="mt-1.5 text-[12.5px] leading-relaxed text-ink-dim">
                  <span className="font-medium text-ink">Fix — </span>
                  {r.fix}
                </p>
                <div className="mt-3 flex items-center gap-3">
                  <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-bg-sunken">
                    <div
                      className={cn("h-full rounded-full bg-accent transition-all")}
                      style={{ width: progressWidth[r.progress] }}
                    />
                  </div>
                  <span className="shrink-0 text-[11.5px] capitalize text-ink-faint">{r.progress}</span>
                </div>
              </CardContent>
            </Card>
          </Reveal>
        ))}
      </div>
    </div>
  );
}
