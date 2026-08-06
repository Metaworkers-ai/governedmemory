import { PageHeader } from "@/components/features/page-header";
import { Reveal } from "@/components/features/reveal";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { CheckCircle2, AlertTriangle, XCircle } from "lucide-react";

const working = [
  "Per-tenant Bearer API-key auth: tenant_id is always resolved server-side from GOVERNEDMEMORY_API_KEYS, never accepted from a client body (api/auth.py, api/schemas.py).",
  "Write-time governance: duplicate detection and prompt-injection scoring run inside MemoryStore.write() before anything is persisted (core/write_governor, core/detection).",
  "Hash-chained, append-only audit log with a working (if unrouted) chain verifier (core/audit).",
  "Tiered embedding fallback — OpenAI, then local sentence-transformers, then zero-vectors — so the server always starts (api/main.py:_build_embedder).",
  "web/, a real Next.js console, already talks to the REST API over HTTP with the Bearer-key pattern for write/browse/search/governance/audit.",
];

const partial = [
  "core/policy_engine's policy management (get_policy/upsert_policy/check_privilege) and core/audit's chain verifier are fully implemented on MemoryStore but have no REST route yet.",
  "CohereEmbeddingProvider is implemented (core/memory_store/embeddings.py) but unreachable — api/main.py's fallback chain never selects it.",
  "web/app/signup/page.tsx exists and looks functional, but is an explicit UI-only stub waiting on an account-creation endpoint that doesn't exist.",
];

const missing = [
  "No rate limiting on any route, and no CORS middleware configured at all in api/main.py.",
  "No user-account system anywhere — auth is one static API key per tenant, by design (\"self-host, zero extra infra\").",
  "No observability/tracing library (OpenTelemetry or otherwise) declared or imported anywhere in api/ or core/.",
  "EMBEDDING_MODEL is documented in deploy/.env.example but never actually read — SentenceTransformerProvider() is called with no override.",
];

function Group({
  icon: Icon,
  tone,
  title,
  items,
}: {
  icon: typeof CheckCircle2;
  tone: "good" | "warn" | "crit";
  title: string;
  items: string[];
}) {
  const colorClass = tone === "good" ? "text-good" : tone === "warn" ? "text-warn" : "text-crit";
  return (
    <Card>
      <CardHeader>
        <div className="flex items-center gap-2">
          <Icon className={`h-4 w-4 ${colorClass}`} />
          <CardTitle>{title}</CardTitle>
          <Badge tone={tone} className="ml-auto">
            {items.length}
          </Badge>
        </div>
      </CardHeader>
      <CardContent>
        <ul className="flex flex-col gap-3">
          {items.map((item, i) => (
            <li key={i} className="flex gap-2.5 text-[13px] leading-relaxed text-ink-dim">
              <span className={`mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full ${tone === "good" ? "bg-good" : tone === "warn" ? "bg-warn" : "bg-crit"}`} />
              {item}
            </li>
          ))}
        </ul>
      </CardContent>
    </Card>
  );
}

export default function ExecutiveSummaryPage() {
  return (
    <div>
      <PageHeader
        eyebrow="01 · Executive summary"
        title="What's real, what's aspirational"
        description="GovernedMemory is a governed agent-memory store behind a FastAPI REST API — write-time injection scanning, purpose-bound retrieval, and a hash-chained audit log, self-hosted on Postgres+pgvector with no user-account system."
      />
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Reveal index={0}>
          <Group icon={CheckCircle2} tone="good" title="Working" items={working} />
        </Reveal>
        <Reveal index={1}>
          <Group icon={AlertTriangle} tone="warn" title="Partial" items={partial} />
        </Reveal>
        <Reveal index={2}>
          <Group icon={XCircle} tone="crit" title="Missing" items={missing} />
        </Reveal>
      </div>
    </div>
  );
}
