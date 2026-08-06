import { PageHeader } from "@/components/features/page-header";
import { Reveal } from "@/components/features/reveal";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { StatusBadge } from "@/components/ui/badge";
import { backendModules, repoMeta } from "@/data/report";

export default function BackendPage() {
  return (
    <div>
      <PageHeader
        eyebrow="03 · Backend architecture"
        title={`${repoMeta.backendStack} surface over a governed memory store`}
        description="api/ is a thin REST layer (auth, request/response schemas) over core/memory_store, which does the real work: write-time governance, retrieval fusion, and a hash-chained audit log, all on raw psycopg2 + Postgres/pgvector."
      />

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {backendModules.map((m, i) => (
          <Reveal index={i} key={m.name}>
            <Card className="h-full">
              <CardHeader>
                <div className="flex items-center justify-between gap-2">
                  <CardTitle className="font-mono text-[13.5px]">{m.name}</CardTitle>
                  <StatusBadge status={m.status} />
                </div>
                <CardDescription className="font-mono text-[11px] text-ink-faint">{m.path}</CardDescription>
              </CardHeader>
              <CardContent>
                <p className="mb-2 text-[11px] font-medium uppercase tracking-wide text-accent">{m.role}</p>
                <p className="text-[13px] leading-relaxed text-ink-dim">{m.description}</p>
                {m.dependsOn && (
                  <div className="mt-3 flex flex-wrap gap-1.5">
                    {m.dependsOn.map((d) => (
                      <span key={d} className="rounded border border-border-soft bg-bg-sunken px-1.5 py-0.5 font-mono text-[10.5px] text-ink-dim">
                        → {d}
                      </span>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          </Reveal>
        ))}
      </div>
    </div>
  );
}
