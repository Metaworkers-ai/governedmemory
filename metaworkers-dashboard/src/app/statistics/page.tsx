import { PageHeader } from "@/components/features/page-header";
import { Reveal } from "@/components/features/reveal";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { CategoryBars } from "@/components/features/charts";
import { repoStats, repoMeta } from "@/data/report";
import { getStats, isBackendUp } from "@/lib/backend";

// Fetches live backend data per request — must not be frozen at build time.
export const dynamic = "force-dynamic";

const statEntries = [
  { label: "Tracked files", value: repoStats.files },
  { label: "Directories", value: repoStats.directories },
  { label: "Lines of code", value: repoStats.linesOfCode },
  { label: "API routes", value: repoStats.routes },
  { label: "Packages", value: repoStats.packages },
  { label: "Prompt files", value: repoStats.promptFiles },
  { label: "Env variables", value: repoStats.envVars },
  { label: "Security findings", value: repoStats.securityFindings },
  { label: "Integrations", value: repoStats.integrations },
  { label: "Workers", value: repoStats.workers },
];

const chartData = [
  { name: "Routes", value: repoStats.routes },
  { name: "Packages", value: repoStats.packages },
  { name: "Env vars", value: repoStats.envVars },
  { name: "Findings", value: repoStats.securityFindings },
  { name: "Integrations", value: repoStats.integrations },
];

export default async function StatisticsPage() {
  const [stats, backendUp] = await Promise.all([getStats(), isBackendUp()]);

  return (
    <div>
      <PageHeader
        eyebrow="17 · Repository statistics"
        title="At a glance"
        description={`${repoMeta.owner}/${repoMeta.name} · commit ${repoMeta.commit} · ${repoMeta.trackedFiles} tracked files.`}
        actions={<Badge tone={backendUp ? "good" : "outline"}>{backendUp ? "Backend live" : "Backend not connected"}</Badge>}
      />

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
        {statEntries.map((s, i) => (
          <Reveal index={i} key={s.label}>
            <div className="rounded-[var(--radius)] border border-border bg-bg-elevated p-4 text-center shadow-[var(--shadow-sm)]">
              <p className="font-mono text-2xl font-semibold text-ink tabular-nums">{s.value.toLocaleString()}</p>
              <p className="mt-1 text-[11px] uppercase tracking-wide text-ink-faint">{s.label}</p>
            </div>
          </Reveal>
        ))}
      </div>

      {stats && (
        <Reveal index={statEntries.length} className="mt-4">
          <Card>
            <CardHeader>
              <CardTitle>Live from GET /v1/stats</CardTitle>
            </CardHeader>
            <CardContent className="grid grid-cols-2 gap-3 sm:grid-cols-3">
              <div className="rounded-[var(--radius)] border border-border bg-bg-elevated p-4 text-center">
                <p className="font-mono text-2xl font-semibold text-ink tabular-nums">{stats.total_memories}</p>
                <p className="mt-1 text-[11px] uppercase tracking-wide text-ink-faint">Total memories</p>
              </div>
              <div className="rounded-[var(--radius)] border border-border bg-bg-elevated p-4 text-center">
                <p className="font-mono text-2xl font-semibold text-ink tabular-nums">{stats.total_customers}</p>
                <p className="mt-1 text-[11px] uppercase tracking-wide text-ink-faint">Total customers</p>
              </div>
              <div className="rounded-[var(--radius)] border border-border bg-bg-elevated p-4 text-center">
                <p className="truncate font-mono text-[13px] font-semibold text-ink">{stats.tenant_id}</p>
                <p className="mt-1 text-[11px] uppercase tracking-wide text-ink-faint">Tenant</p>
              </div>
            </CardContent>
          </Card>
        </Reveal>
      )}

      <Reveal index={statEntries.length + 1} className="mt-4">
        <Card>
          <CardHeader>
            <CardTitle>Surface area by count</CardTitle>
          </CardHeader>
          <CardContent>
            <CategoryBars data={chartData} />
          </CardContent>
        </Card>
      </Reveal>
    </div>
  );
}
