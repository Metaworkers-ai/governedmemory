"use client";

import { useState } from "react";

import { EmptyState, TaintBadge } from "@/components/ui";
import type { MemoryRecord } from "@/lib/types";

export function MemoryList({ memories }: { memories: MemoryRecord[] }) {
  const [openId, setOpenId] = useState<string | null>(null);

  if (memories.length === 0) {
    return <EmptyState>No memories yet.</EmptyState>;
  }

  return (
    <div className="divide-y divide-neutral-100 overflow-hidden rounded-lg border border-neutral-200 bg-white">
      {memories.map((m) => {
        const open = openId === m.id;
        return (
          <div key={m.id}>
            <button
              type="button"
              onClick={() => setOpenId(open ? null : m.id)}
              className="flex w-full items-center gap-3 px-4 py-3 text-left text-sm hover:bg-neutral-50"
            >
              <TaintBadge taint={m.trust.taint} />
              <span className="flex-1 truncate text-neutral-800">{m.content}</span>
              {m.temporal.superseded_by && (
                <span className="shrink-0 text-xs text-neutral-400">superseded</span>
              )}
              <code className="shrink-0 text-xs text-neutral-400">{m.id.slice(0, 8)}</code>
            </button>
            {open && (
              <pre className="overflow-x-auto bg-neutral-50 px-4 py-3 text-xs text-neutral-700">
                {JSON.stringify(m, null, 2)}
              </pre>
            )}
          </div>
        );
      })}
    </div>
  );
}
