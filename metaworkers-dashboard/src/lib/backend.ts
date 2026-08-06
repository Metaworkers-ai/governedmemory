import "server-only";

// This dashboard is a read-only console for the GovernedMemory REST API
// (see ../../../api/main.py in the governedmemory repo). Auth is a single
// per-tenant Bearer API key (api/auth.py) -- there's no user login, so
// GOVERNEDMEMORY_API_KEY configures which tenant this deployment views.
// GOVERNEDMEMORY_API_KEY must never be NEXT_PUBLIC_-prefixed; the
// `server-only` import above turns an accidental client-component import
// of this file into a build error rather than a runtime key leak.

const REQUEST_TIMEOUT_MS = 8_000;

function config(): { baseUrl: string; apiKey: string } | null {
  const baseUrl = process.env.GOVERNEDMEMORY_API_URL;
  const apiKey = process.env.GOVERNEDMEMORY_API_KEY;
  if (!baseUrl || !apiKey) return null;
  return { baseUrl: baseUrl.replace(/\/$/, ""), apiKey };
}

export function isBackendConfigured(): boolean {
  return config() !== null;
}

// Every call is best-effort: a missing config, unreachable backend, or
// non-2xx response all resolve to `null` rather than throwing, so pages can
// render an EmptyState/"not connected" badge instead of crashing.
async function backendFetch<T>(path: string, opts?: { auth?: boolean }): Promise<T | null> {
  const cfg = config();
  if (!cfg) return null;

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  try {
    const res = await fetch(cfg.baseUrl + path, {
      headers: opts?.auth === false ? {} : { Authorization: `Bearer ${cfg.apiKey}` },
      cache: "no-store",
      signal: controller.signal,
    });
    if (!res.ok) return null;
    return (await res.json()) as T;
  } catch {
    return null;
  } finally {
    clearTimeout(timeout);
  }
}

export interface BackendStats {
  tenant_id: string;
  total_memories: number;
  total_customers: number;
}

export function getStats(): Promise<BackendStats | null> {
  return backendFetch<BackendStats>("/v1/stats");
}

export interface CustomerSummary {
  customer_id: string;
  memory_count: number;
}

export function listCustomers(): Promise<CustomerSummary[] | null> {
  return backendFetch<CustomerSummary[]>("/v1/customers");
}

// /healthz and /openapi.json need no tenant key (healthz has no auth
// dependency at all; /openapi.json is FastAPI's built-in schema route).
export async function isBackendUp(): Promise<boolean> {
  const result = await backendFetch<{ status: string }>("/healthz", { auth: false });
  return result?.status === "ok";
}

export interface OpenApiOperation {
  summary?: string;
  description?: string;
  tags?: string[];
  operationId?: string;
}

export interface OpenApiSpec {
  paths: Record<string, Record<string, OpenApiOperation>>;
}

export function getOpenApiSpec(): Promise<OpenApiSpec | null> {
  return backendFetch<OpenApiSpec>("/openapi.json", { auth: false });
}
