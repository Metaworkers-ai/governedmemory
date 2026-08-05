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
    <div className="divide-y divide-[var(--color-border)] overflow-hidden rounded-2xl border border-[var(--color-border)] bg-white shadow-sm">
      {memories.map((m) => {
        const open = openId === m.id;
        return (
          <div key={m.id}>
            <button
              type="button"
              onClick={() => setOpenId(open ? null : m.id)}
              className="flex w-full items-center gap-3 px-4 py-3.5 text-left text-sm transition-colors hover:bg-slate-50"
            >
              <TaintBadge taint={m.trust.taint} />
              <span className="flex-1 truncate text-[var(--color-text)]">{m.content}</span>
              {m.temporal.superseded_by && (
                <span className="shrink-0 rounded-full bg-slate-100 px-2 py-0.5 text-xs text-[var(--color-muted)]">
                  superseded
                </span>
              )}
              <code className="shrink-0 text-xs text-[var(--color-muted)]">{m.id.slice(0, 8)}</code>
              <svg
                viewBox="0 0 24 24"
                fill="none"
                className={`h-4 w-4 shrink-0 text-[var(--color-muted)] transition-transform ${open ? "rotate-180" : ""}`}
                aria-hidden="true"
              >
                <path d="m6 9 6 6 6-6" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </button>
            {open && (
              <pre className="animate-fade-in overflow-x-auto bg-slate-50 px-4 py-3 text-xs text-[var(--color-text)]">
                {JSON.stringify(m, null, 2)}
              </pre>
            )}
          </div>
        );
      })}
    </div>
  );
}
