import "server-only";

import type {
  AuditEvent,
  CustomerSummary,
  MemoryRecord,
  Provenance,
  Purpose,
} from "./types";
import { BackendError } from "./types";

// Single-tenant-per-deployment: the REST API resolves tenant_id entirely
// from this one Bearer key (see governedmemory/api/auth.py), so this app
// acts as exactly one tenant. GOVERNEDMEMORY_API_KEY must never be
// NEXT_PUBLIC_-prefixed -- the `server-only` import above turns any
// accidental client-component import of this file into a build error.
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

  const res = await fetch(url, {
    method: init?.method ?? "GET",
    headers: {
      Authorization: `Bearer ${apiKey}`,
      "Content-Type": "application/json",
    },
    body: init?.body !== undefined ? JSON.stringify(init.body) : undefined,
    cache: "no-store",
  });

  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body?.detail ?? detail;
    } catch {
      // body wasn't JSON -- fall back to statusText
    }
    throw new BackendError(res.status, detail);
  }

  if (res.status === 204) return undefined as T;
  const text = await res.text();
  return text ? (JSON.parse(text) as T) : (undefined as T);
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
