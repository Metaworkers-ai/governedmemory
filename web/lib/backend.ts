import "server-only";

import { logger } from "./logger";
import type {
  AuditEvent,
  CustomerSummary,
  MemoryRecord,
  Provenance,
  Purpose,
} from "./types";
import { BackendError } from "./types";

const REQUEST_TIMEOUT_MS = 15_000;

// Single-tenant-per-deployment: the REST API resolves tenant_id entirely
// from this one Bearer key (see governedmemory/api/auth.py), so this app
// acts as exactly one tenant. GOVERNEDMEMORY_API_KEY must never be
// NEXT_PUBLIC_-prefixed -- the `server-only` import above turns any
// accidental client-component import of this file into a build error.
//
// instrumentation.ts validates these are set at process startup; this check
// stays as defense-in-depth for the (Edge/serverless) runtimes it can't
// cover, and to give a clear error if this module is ever exercised in a
// unit test without env vars set.
function config() {
  const baseUrl = process.env.GOVERNEDMEMORY_API_URL;
  const apiKey = process.env.GOVERNEDMEMORY_API_KEY;
  if (!baseUrl || !apiKey) {
    throw new Error(
      "GOVERNEDMEMORY_API_URL and GOVERNEDMEMORY_API_KEY must be set (see web/.env.example)",
    );
  }
  return { baseUrl: baseUrl.replace(/\/$/, ""), apiKey };
}

async function backendFetch<T>(
  path: string,
  init?: { method?: string; body?: unknown; query?: Record<string, string | number | boolean | undefined> },
): Promise<T> {
  const { baseUrl, apiKey } = config();
  const url = new URL(baseUrl + path);
  if (init?.query) {
    for (const [key, value] of Object.entries(init.query)) {
      if (value !== undefined) url.searchParams.set(key, String(value));
    }
  }

  const method = init?.method ?? "GET";
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

  let res: Response;
  try {
    res = await fetch(url, {
      method,
      headers: {
        Authorization: `Bearer ${apiKey}`,
        "Content-Type": "application/json",
      },
      body: init?.body !== undefined ? JSON.stringify(init.body) : undefined,
      cache: "no-store",
      signal: controller.signal,
    });
  } catch (err) {
    const timedOut = err instanceof Error && err.name === "AbortError";
    logger.error("backend request failed", err, { method, path: url.pathname });
    throw new BackendError(
      0,
      timedOut
        ? "The GovernedMemory API took too long to respond. Please try again."
        : "Unable to reach the GovernedMemory API. Check that the backend is running and GOVERNEDMEMORY_API_URL is correct.",
    );
  } finally {
    clearTimeout(timeout);
  }

  if (!res.ok) {
    let detail = res.statusText || `Request failed with status ${res.status}`;
    try {
      const body = await res.json();
      detail = body?.detail ?? detail;
    } catch {
      // body wasn't JSON -- fall back to statusText
    }
    logger.warn("backend returned an error response", {
      method,
      path: url.pathname,
      status: res.status,
      detail,
    });
    throw new BackendError(res.status, detail);
  }

  if (res.status === 204) return undefined as T;
  const text = await res.text();
  if (!text) return undefined as T;
  try {
    return JSON.parse(text) as T;
  } catch (err) {
    logger.error("backend returned unparseable JSON", err, { method, path: url.pathname });
    throw new BackendError(res.status, "The API returned an unexpected response.");
  }
}

export interface WriteMemoryInput {
  customer_id: string;
  agent_id: string;
  session_id: string;
  content: string;
  provenance: Provenance;
  purpose?: Purpose;
}

export function writeMemory(input: WriteMemoryInput): Promise<MemoryRecord> {
  return backendFetch<MemoryRecord>("/v1/memory", { method: "POST", body: input });
}

export interface RetrieveInput {
  query: string;
  agent_id: string;
  session_id: string;
  purpose?: string | null;
  k?: number;
  include_untrusted?: boolean;
}

export function retrieveMemories(input: RetrieveInput): Promise<MemoryRecord[]> {
  return backendFetch<MemoryRecord[]>("/v1/retrieve", { method: "POST", body: input });
}

export function quarantineMemory(memoryId: string, reason: string): Promise<{ success: boolean }> {
  return backendFetch("/v1/quarantine", {
    method: "POST",
    body: { memory_id: memoryId, reason },
  });
}

export function deleteMemory(memoryId: string, cascade = false): Promise<{ success: boolean }> {
  return backendFetch(`/v1/memory/${encodeURIComponent(memoryId)}`, {
    method: "DELETE",
    query: { cascade },
  });
}

export function listAudit(limit = 50): Promise<AuditEvent[]> {
  return backendFetch<AuditEvent[]>("/v1/audit", { query: { limit } });
}

export function listCustomers(): Promise<CustomerSummary[]> {
  return backendFetch<CustomerSummary[]>("/v1/customers");
}

export function listMemoriesForCustomer(customerId: string): Promise<MemoryRecord[]> {
  return backendFetch<MemoryRecord[]>("/v1/memories", { query: { customer_id: customerId } });
}
