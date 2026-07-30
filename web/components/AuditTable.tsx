"use client";

import { useMemo, useState } from "react";

import { Chip, EmptyState, Input, OutcomeBadge } from "@/components/ui";
import type { AuditEvent } from "@/lib/types";

const OUTCOME_ICON: Record<string, string> = {
  allow: "✓",
  deny: "✕",
  gated: "⚠",
};

export function AuditTable({ events }: { events: AuditEvent[] }) {
  const [outcomeFilter, setOutcomeFilter] = useState<string | null>(null);
  const [query, setQuery] = useState("");

  const outcomes = useMemo(() => Array.from(new Set(events.map((e) => e.outcome))), [events]);

  const filtered = useMemo(() => {
    return events.filter((e) => {
      if (outcomeFilter && e.outcome !== outcomeFilter) return false;
      if (query) {
        const q = query.toLowerCase();
        const haystack = `${e.op} ${e.agent_id} ${e.session_id} ${e.reason ?? ""}`.toLowerCase();
        if (!haystack.includes(q)) return false;
      }
      return true;
    });
  }, [events, outcomeFilter, query]);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <div className="relative w-full max-w-sm">
          <svg
            viewBox="0 0 24 24"
            fill="none"
            className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--color-muted)]"
            aria-hidden="true"
          >
            <circle cx="11" cy="11" r="7" stroke="currentColor" strokeWidth="1.7" />
            <path d="m20 20-3-3" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" />
          </svg>
          <Input
            className="pl-10"
            placeholder="Filter by op, agent, session, reason…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Chip active={outcomeFilter === null} onClick={() => setOutcomeFilter(null)}>
            All
          </Chip>
          {outcomes.map((o) => (
            <Chip key={o} active={outcomeFilter === o} onClick={() => setOutcomeFilter(o)}>
              {o}
            </Chip>
          ))}
        </div>
      </div>

      {filtered.length === 0 ? (
        <EmptyState>No audit events match.</EmptyState>
      ) : (
        <div className="overflow-hidden rounded-2xl border border-[var(--color-border)] bg-white shadow-sm">
          <div className="max-h-[70vh] overflow-auto">
            <table className="w-full text-sm">
              <thead className="sticky top-0 z-10 bg-slate-50 text-left text-xs uppercase tracking-wide text-[var(--color-muted)]">
                <tr>
                  <th className="px-4 py-3 font-medium">Time</th>
                  <th className="px-4 py-3 font-medium">Op</th>
                  <th className="px-4 py-3 font-medium">Outcome</th>
                  <th className="px-4 py-3 font-medium">Agent / Session</th>
                  <th className="px-4 py-3 font-medium">Hash</th>
                  <th className="px-4 py-3 font-medium">Prev hash</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--color-border)]">
                {filtered.map((e) => (
                  <tr key={e.id} className="transition-colors hover:bg-slate-50">
                    <td className="whitespace-nowrap px-4 py-3 text-[var(--color-muted)]">
                      {new Date(e.ts).toLocaleString()}
                    </td>
                    <td className="px-4 py-3 font-medium text-[var(--color-text)]">{e.op}</td>
                    <td className="px-4 py-3">
                      <span className="inline-flex items-center gap-1.5">
                        <span aria-hidden="true">{OUTCOME_ICON[e.outcome] ?? "•"}</span>
                        <OutcomeBadge outcome={e.outcome} />
                      </span>
                    </td>
                    <td className="px-4 py-3 text-[var(--color-muted)]">
                      {e.agent_id} / {e.session_id}
                    </td>
                    <td className="px-4 py-3 font-mono text-xs text-[var(--color-muted)]">
                      {e.hash.slice(0, 12)}…
                    </td>
                    <td className="px-4 py-3 font-mono text-xs text-[var(--color-muted)]">
                      {e.prev_hash.slice(0, 12)}…
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
