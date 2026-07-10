"use server";

// No revalidatePath() calls here on purpose: every read in this app uses
// cache: "no-store" (lib/backend.ts) with force-dynamic pages, so nothing is
// ever cached to invalidate. revalidatePath also forces a re-render of the
// *calling* route as part of the action's response (a "seeded navigation"),
// which was resetting this page's own client state after a successful
// mutation -- a worse outcome than the staleness it would have prevented.

import * as backend from "@/lib/backend";
import type { MemoryRecord } from "@/lib/types";
import { BackendError } from "@/lib/types";

export type ActionResult<T> = { ok: true; data: T } | { ok: false; error: string };

function toResult<T>(promise: Promise<T>): Promise<ActionResult<T>> {
  return promise
    .then((data) => ({ ok: true as const, data }))
    .catch((err) => ({
      ok: false as const,
      error: err instanceof BackendError ? err.detail : "Unexpected error contacting the API",
    }));
}

export async function writeMemoryAction(input: {
  customer_id: string;
  agent_id: string;
  session_id: string;
  content: string;
  source_type: string;
  source_ref: string;
  confidence: number;
  allowed_purposes: string[];
}): Promise<ActionResult<MemoryRecord>> {
  const result = await toResult(
    backend.writeMemory({
      customer_id: input.customer_id,
      agent_id: input.agent_id,
      session_id: input.session_id,
      content: input.content,
      provenance: {
        source_type: input.source_type as never,
        source_ref: input.source_ref,
        confidence: input.confidence,
        ingested_at: new Date().toISOString(),
        parent_ids: [],
      },
      purpose: { allowed_purposes: input.allowed_purposes, policy_id: "default" },
    }),
  );
  return result;
}

export async function quarantineMemoryAction(
  memoryId: string,
  reason: string,
): Promise<ActionResult<{ success: boolean }>> {
  return toResult(backend.quarantineMemory(memoryId, reason));
}

export async function deleteMemoryAction(memoryId: string): Promise<ActionResult<{ success: boolean }>> {
  return toResult(backend.deleteMemory(memoryId));
}

export async function listMemoriesAction(customerId: string): Promise<ActionResult<MemoryRecord[]>> {
  return toResult(backend.listMemoriesForCustomer(customerId));
}

export async function retrieveAction(input: {
  query: string;
  agent_id: string;
  session_id: string;
  purpose?: string | null;
  k?: number;
  include_untrusted?: boolean;
}): Promise<ActionResult<MemoryRecord[]>> {
  return toResult(backend.retrieveMemories(input));
}
