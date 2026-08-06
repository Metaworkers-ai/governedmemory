import { PageHeader } from "@/components/features/page-header";
import { KpiCard } from "@/components/features/kpi-card";
import { ScoreGauge } from "@/components/features/score-gauge";
import { Reveal } from "@/components/features/reveal";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge, StatusBadge } from "@/components/ui/badge";
import {
  kpis,
  repoMeta,
  repoScore,
  aiProviders,
  packages,
  backendModules,
  securityFindings,
} from "@/data/report";
import { getStats, isBackendUp } from "@/lib/backend";

// Fetches live backend data per request — must not be frozen at build time.
export const dynamic = "force-dynamic";
import {
  GitBranch,
  Sparkles,
  Server,
  Route,
  KeyRound,
  ShieldAlert,
  Gauge,
  Files,
  Code2,
} from "lucide-react";

const icons = [
  GitBranch,
  GitBranch,
  Files,
  Code2,
  Sparkles,
  Server,
  Route,
  KeyRound,
  ShieldAlert,
  Gauge,
];

const techStack = [
  { name: "FastAPI", role: "REST surface (api/)", status: "working" as const },
  { name: "Next.js (App Router)", role: "web/ console + this dashboard", status: "working" as const },
  { name: "Postgres + pgvector", role: "Persistence, vector + lexical search", status: "working" as const },
  { name: "OpenAI / local / null embeddings", role: "Tiered semantic-search fallback", status: "working" as const },
  { name: "Rate limiting", role: "No middleware/dependency present", status: "missing" as const },
  { name: "User accounts", role: "Not present — single API key per tenant", status: "missing" as const },
];

export default async function DashboardHome() {
  const [stats, backendUp] = await Promise.all([getStats(), isBackendUp()]);
  return (
    <div>
      <PageHeader
        eyebrow="Repository analysis"
        title={`${repoMeta.owner}/${repoMeta.name}`}
        description={`Evidence-based review of branch ${repoMeta.branch}, commit ${repoMeta.commit}. Every figure on this page traces back to a file in the repository.`}
        actions={
          <div className="flex items-center gap-2">
            <Badge tone={backendUp ? "good" : "outline"}>{backendUp ? "Backend live" : "Backend not connected"}</Badge>
            <Badge tone="outline">Last commit {repoMeta.lastCommitDate}</Badge>
          </div>
        }
      />

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-6">
        {kpis.map((item, i) => (
          <KpiCard key={item.label} item={item} icon={icons[i]} index={i} />
        ))}
      </div>

      {stats && (
        <Reveal index={1} className="mt-4">
          <Card>
            <CardContent className="flex flex-wrap items-center gap-6 p-4">
              <div>
                <p className="text-[11px] uppercase tracking-wide text-ink-faint">Live · tenant</p>
                <p className="font-mono text-[13px] text-ink">{stats.tenant_id}</p>
              </div>
              <div>
                <p className="text-[11px] uppercase tracking-wide text-ink-faint">Total memories</p>
                <p className="font-mono text-xl font-semibold text-ink tabular-nums">{stats.total_memories}</p>
              </div>
              <div>
                <p className="text-[11px] uppercase tracking-wide text-ink-faint">Total customers</p>
                <p className="font-mono text-xl font-semibold text-ink tabular-nums">{stats.total_customers}</p>
              </div>
              <p className="ml-auto text-[12px] text-ink-faint">GET /v1/stats</p>
            </CardContent>
          </Card>
        </Reveal>
      )}

      <div className="mt-6 grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Reveal index={2} className="lg:col-span-1">
          <Card className="h-full">
            <CardHeader>
              <CardTitle>Code quality score</CardTitle>
              <CardDescription>Weighted across implementation completeness, test discipline, and security posture.</CardDescription>
            </CardHeader>
            <CardContent className="flex items-center gap-5">
              <ScoreGauge score={repoScore} />
              <div className="flex flex-col gap-2">
                <Badge tone="good">+ hash-chained, append-only audit log</Badge>
                <Badge tone="good">+ write-time injection scoring</Badge>
                <Badge tone="warn">− no rate limiting or CORS config</Badge>
                <Badge tone="crit">− no key rotation/revocation path</Badge>
              </div>
            </CardContent>
          </Card>
        </Reveal>

        <Reveal index={3} className="lg:col-span-2">
          <Card className="h-full">
            <CardHeader>
              <CardTitle>Repository health</CardTitle>
              <CardDescription>
                Live/stub status across the {backendModules.length} backend modules and {securityFindings.length} security findings.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                {backendModules.slice(0, 6).map((m) => (
                  <div key={m.name} className="flex items-center justify-between gap-2 rounded-lg border border-border-soft bg-bg-sunken px-3 py-2">
                    <span className="truncate font-mono text-[12.5px] text-ink">{m.name}</span>
                    <StatusBadge status={m.status} />
                  </div>
                ))}
              </div>
              <div className="mt-3 flex flex-wrap gap-2 text-[12px] text-ink-dim">
                <span>{aiProviders.length} AI provider</span>
                <span className="text-ink-faint">·</span>
                <span>{packages.length} packages tracked</span>
                <span className="text-ink-faint">·</span>
                <span>{securityFindings.length} open findings, 0 critical</span>
              </div>
            </CardContent>
          </Card>
        </Reveal>
      </div>

      <Reveal index={4} className="mt-4">
        <Card>
          <CardHeader>
            <CardTitle>Technology stack</CardTitle>
            <CardDescription>What&apos;s actually running versus declared-but-dormant.</CardDescription>
          </CardHeader>
          <CardContent className="grid grid-cols-1 gap-2 sm:grid-cols-2 xl:grid-cols-3">
            {techStack.map((t) => (
              <div key={t.name} className="flex items-start justify-between gap-3 rounded-lg border border-border-soft bg-bg-sunken px-3.5 py-3">
                <div className="min-w-0">
                  <p className="truncate text-[13px] font-semibold text-ink">{t.name}</p>
                  <p className="text-[12px] text-ink-dim">{t.role}</p>
                </div>
                <StatusBadge status={t.status} />
              </div>
            ))}
          </CardContent>
        </Card>
      </Reveal>
    </div>
  );
}
