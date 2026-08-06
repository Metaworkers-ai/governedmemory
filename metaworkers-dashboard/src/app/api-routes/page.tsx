import { PageHeader } from "@/components/features/page-header";
import { Reveal } from "@/components/features/reveal";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/features/empty-state";
import { notMountedRoutes } from "@/data/report";
import { getOpenApiSpec, isBackendConfigured } from "@/lib/backend";
import type { ApiRoute } from "@/types/report";
import { PlugZap } from "lucide-react";
import { RoutesExplorer } from "./routes-explorer";

// Fetches live backend data per request — must not be frozen at build time.
export const dynamic = "force-dynamic";

const HTTP_METHODS = ["get", "post", "put", "delete"] as const;

function toApiRoutes(spec: Awaited<ReturnType<typeof getOpenApiSpec>>): ApiRoute[] {
  if (!spec?.paths) return [];
  const routes: ApiRoute[] = [];
  for (const [path, operations] of Object.entries(spec.paths)) {
    for (const method of HTTP_METHODS) {
      const op = operations[method];
      if (!op) continue;
      routes.push({
        method: method.toUpperCase() as ApiRoute["method"],
        route: path,
        module: "api/main.py",
        purpose: op.summary ?? op.operationId ?? path,
        // Every route except /healthz depends on require_tenant (api/auth.py) —
        // a fixed fact about api/main.py, not something openapi.json encodes.
        authRequired: path !== "/healthz",
        status: "working",
        description: op.description ?? op.summary ?? "",
      });
    }
  }
  return routes.sort((a, b) => a.route.localeCompare(b.route));
}

export default async function ApiRoutesPage() {
  const configured = isBackendConfigured();
  const spec = await getOpenApiSpec();
  const routes = toApiRoutes(spec);
  const connected = routes.length > 0;

  return (
    <div>
      <PageHeader
        eyebrow="08 · API routes"
        title={connected ? `${routes.length} live FastAPI routes` : "Not connected to a backend"}
        description={
          connected
            ? "Fetched live from the backend's /openapi.json (api/main.py) — always in sync with the running server. Click a row for details."
            : configured
              ? "GOVERNEDMEMORY_API_URL/GOVERNEDMEMORY_API_KEY are set, but the backend didn't respond. Start it with `make api` or docker compose, then reload."
              : "Set GOVERNEDMEMORY_API_URL and GOVERNEDMEMORY_API_KEY (see .env.local.example) and start the backend to list its live routes here."
        }
        actions={connected ? <Badge tone="good">Backend reachable</Badge> : <Badge tone="warn">Backend unreachable</Badge>}
      />

      {connected ? (
        <Reveal index={0}>
          <RoutesExplorer routes={routes} />
        </Reveal>
      ) : (
        <Reveal index={0}>
          <EmptyState
            icon={PlugZap}
            title="No live route data"
            description="This page has no hardcoded route list by design — it only ever shows what the running backend actually serves."
          />
        </Reveal>
      )}

      <Reveal index={1} className="mt-4">
        <Card className="p-4">
          <p className="mb-2 text-[13px] font-semibold text-ink">Implemented but not routed</p>
          <div className="flex flex-col gap-1.5">
            {notMountedRoutes.map((r) => (
              <div key={r.path} className="flex flex-wrap items-center gap-2 text-[12.5px] text-ink-dim">
                <span className="font-mono text-warn">{r.path}</span>
                <span className="text-ink-faint">—</span>
                <span>{r.note}</span>
              </div>
            ))}
          </div>
        </Card>
      </Reveal>
    </div>
  );
}
