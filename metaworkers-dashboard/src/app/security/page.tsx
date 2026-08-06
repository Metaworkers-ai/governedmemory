import { PageHeader } from "@/components/features/page-header";
import { Reveal } from "@/components/features/reveal";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ScoreGauge } from "@/components/features/score-gauge";
import { SeverityBadge } from "@/components/features/severity-badge";
import { CategoryBars } from "@/components/features/charts";
import { securityFindings, securityClean, severityCounts, securityScore } from "@/data/report";
import { CheckCircle2 } from "lucide-react";

const severityData = [
  { name: "Critical", value: severityCounts.critical },
  { name: "High", value: severityCounts.high },
  { name: "Medium", value: severityCounts.medium },
  { name: "Low", value: severityCounts.low },
];

export default function SecurityPage() {
  return (
    <div>
      <PageHeader
        eyebrow="14 · Security audit"
        title="4 findings — 0 critical, 0 high"
        description="Ranked by severity. The codebase's webhook signature handling is a genuine positive; the open items are hardening work, not active exploits."
      />

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Reveal index={0}>
          <Card className="flex h-full flex-col items-center justify-center gap-3 p-6">
            <ScoreGauge score={securityScore} />
            <p className="text-center text-[12.5px] text-ink-dim">Security score</p>
          </Card>
        </Reveal>

        <Reveal index={1} className="lg:col-span-2">
          <Card className="h-full">
            <CardHeader>
              <CardTitle>Severity distribution</CardTitle>
            </CardHeader>
            <CardContent>
              <CategoryBars data={severityData} height={180} />
            </CardContent>
          </Card>
        </Reveal>
      </div>

      <div className="mt-4 flex flex-col gap-3">
        {securityFindings.map((f, i) => (
          <Reveal index={i} key={f.id}>
            <Card>
              <CardContent className="p-4">
                <div className="flex flex-wrap items-center gap-2">
                  <SeverityBadge severity={f.severity} />
                  <p className="text-[14px] font-semibold text-ink">{f.title}</p>
                  <Badge tone="outline" className="ml-auto">
                    {f.id}
                  </Badge>
                </div>
                <p className="mt-2 text-[13px] leading-relaxed text-ink-dim">{f.description}</p>
                <div className="mt-3 grid grid-cols-1 gap-2 rounded-lg border border-border-soft bg-bg-sunken p-3 text-[12px] sm:grid-cols-2">
                  <div>
                    <p className="mb-0.5 font-medium uppercase tracking-wide text-ink-faint">Evidence</p>
                    <p className="font-mono text-ink-dim">{f.evidence}</p>
                  </div>
                  <div>
                    <p className="mb-0.5 font-medium uppercase tracking-wide text-ink-faint">File</p>
                    <p className="font-mono text-accent">{f.file}</p>
                  </div>
                </div>
                <div className="mt-3 rounded-lg border-l-2 border-accent bg-accent-soft/40 px-3 py-2 text-[12.5px] text-ink">
                  <span className="font-semibold">Fix — </span>
                  {f.recommendation}
                </div>
              </CardContent>
            </Card>
          </Reveal>
        ))}
      </div>

      <Reveal index={securityFindings.length} className="mt-4">
        <Card>
          <CardHeader>
            <CardTitle>Clean on inspection</CardTitle>
            <CardDescription>Reviewed with no issue found.</CardDescription>
          </CardHeader>
          <CardContent className="grid grid-cols-1 gap-2 sm:grid-cols-2">
            {securityClean.map((c) => (
              <div key={c.title} className="flex items-start gap-2 rounded-lg border border-good-border bg-good-bg px-3 py-2.5">
                <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-good" />
                <div>
                  <p className="text-[12.5px] font-medium text-ink">{c.title}</p>
                  {c.file !== "—" && <p className="font-mono text-[11px] text-ink-faint">{c.file}</p>}
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
      </Reveal>
    </div>
  );
}
