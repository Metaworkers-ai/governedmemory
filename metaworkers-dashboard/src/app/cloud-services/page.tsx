import { PageHeader } from "@/components/features/page-header";
import { Reveal } from "@/components/features/reveal";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { StatusBadge } from "@/components/ui/badge";
import { EmptyState } from "@/components/features/empty-state";
import { cloudServices, observability, externalSdks } from "@/data/report";
import { CloudOff, Activity } from "lucide-react";

export default function CloudServicesPage() {
  return (
    <div>
      <PageHeader
        eyebrow="11 · Cloud services & external SDKs"
        title="A managed Postgres, optionally OpenAI"
        description="No AWS/Azure/GCP-specific SDK is used anywhere — this repo's only external dependencies are a Postgres+pgvector database and, optionally, one embedding API."
      />

      <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
        {cloudServices.map((c, i) => (
          <Reveal index={i} key={c.provider}>
            <Card>
              <CardContent className="flex items-start justify-between gap-3 p-4">
                <div className="min-w-0">
                  <p className="text-[13px] font-medium text-ink">{c.provider}</p>
                  <p className="mt-0.5 text-[12px] text-ink-dim">{c.purpose}</p>
                </div>
                <StatusBadge status={c.status} />
              </CardContent>
            </Card>
          </Reveal>
        ))}
      </div>

      <Reveal index={cloudServices.length} className="mt-4">
        <EmptyState
          icon={CloudOff}
          title="No generic cloud-provider SDK"
          description="No AWS SDK, Azure SDK, or Google Cloud client library — deploy/.env.example only documents managed-Postgres connection-string formats for RDS/Cloud SQL/Azure/Supabase, not a provider integration."
        />
      </Reveal>

      <Reveal index={cloudServices.length + 1} className="mt-4">
        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <Activity className="h-4 w-4 text-accent" />
              <CardTitle>Observability</CardTitle>
            </div>
          </CardHeader>
          <CardContent className="flex items-start justify-between gap-3">
            <div>
              <p className="text-[13.5px] font-medium text-ink">{observability.provider}</p>
              <p className="mt-1 text-[12.5px] text-ink-dim">{observability.note}</p>
            </div>
            <StatusBadge status={observability.status} />
          </CardContent>
        </Card>
      </Reveal>

      <Reveal index={cloudServices.length + 2} className="mt-4">
        <Card>
          <CardHeader>
            <CardTitle>External SDKs</CardTitle>
            <CardDescription>Third-party integrations outside the payments/AI surface.</CardDescription>
          </CardHeader>
          <CardContent className="grid grid-cols-1 gap-2 sm:grid-cols-2">
            {externalSdks.map((s) => (
              <div key={s.name} className="flex items-start justify-between gap-3 rounded-lg border border-border-soft bg-bg-sunken px-3 py-2.5">
                <div className="min-w-0">
                  <p className="text-[13px] font-medium text-ink">{s.name}</p>
                  <p className="mt-0.5 text-[12px] text-ink-dim">{s.note}</p>
                </div>
                <StatusBadge status={s.status} />
              </div>
            ))}
          </CardContent>
        </Card>
      </Reveal>
    </div>
  );
}
