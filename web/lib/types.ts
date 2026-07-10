// Mirrors core/models/memory_record.py exactly -- field names, nesting, and
// enum values must match what api/main.py actually serializes.

export type SourceType =
  | "user"
  | "trusted_system"
  | "tool_output"
  | "untrusted_web"
  | "untrusted_email"
  | "agent_derived";

export const SOURCE_TYPES: SourceType[] = [
  "user",
  "trusted_system",
  "tool_output",
  "untrusted_web",
  "untrusted_email",
  "agent_derived",
];

export type Taint = "trusted" | "untrusted" | "quarantined";

export interface Provenance {
  source_type: SourceType;
  source_ref: string;
  ingested_at: string;
  confidence: number;
  parent_ids: string[];
}

export interface Trust {
  taint: Taint;
  taint_reason: string | null;
  injection_score: number;
}

export interface Purpose {
  allowed_purposes: string[];
  policy_id: string;
}

export interface Temporal {
  valid_from: string;
  valid_until: string | null;
  superseded_by: string | null;
  version: number;
}

export interface Access {
  acl: string[];
}

export interface MemoryRecord {
  id: string;
  tenant_id: string;
  customer_id: string;
  agent_id: string;
  session_id: string;
  content: string;
  provenance: Provenance;
  trust: Trust;
  purpose: Purpose;
  temporal: Temporal;
  access: Access;
  created_at: string;
  updated_at: string;
}

export interface CustomerSummary {
  customer_id: string;
  memory_count: number;
  last_activity: string;
}

export interface AuditEvent {
  id: string;
  ts: string;
  agent_id: string;
  session_id: string;
  op: string;
  memory_ids: string[];
  outcome: string;
  reason: string | null;
  policy_id: string | null;
  hash: string;
  prev_hash: string;
}

export class BackendError extends Error {
  constructor(
    public status: number,
    public detail: string,
  ) {
    super(`HTTP ${status}: ${detail}`);
    this.name = "BackendError";
  }
}
