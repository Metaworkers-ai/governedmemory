"use client";

import Link from "next/link";
import { useMemo, useState } from "react";

import { EmptyState, Input, Pagination } from "@/components/ui";
import type { CustomerSummary } from "@/lib/types";

type SortKey = "customer_id" | "memory_count" | "last_activity";

const PAGE_SIZE = 10;

export function CustomerTable({ customers }: { customers: CustomerSummary[] }) {
  const [filter, setFilter] = useState("");
  const [sortKey, setSortKey] = useState<SortKey>("last_activity");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");
  const [page, setPage] = useState(0);

  function toggleSort(key: SortKey) {
    if (key === sortKey) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDir("asc");
    }
    setPage(0);
  }

  const filtered = useMemo(() => {
    const base = filter
      ? customers.filter((c) => c.customer_id.toLowerCase().includes(filter.toLowerCase()))
      : customers;
    const sorted = [...base].sort((a, b) => {
      let cmp = 0;
      if (sortKey === "customer_id") cmp = a.customer_id.localeCompare(b.customer_id);
      else if (sortKey === "memory_count") cmp = a.memory_count - b.memory_count;
      else cmp = new Date(a.last_activity).getTime() - new Date(b.last_activity).getTime();
      return sortDir === "asc" ? cmp : -cmp;
    });
    return sorted;
  }, [customers, filter, sortKey, sortDir]);

  const pageCount = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const safePage = Math.min(page, pageCount - 1);
  const pageItems = filtered.slice(safePage * PAGE_SIZE, safePage * PAGE_SIZE + PAGE_SIZE);

  const columns: { key: SortKey; label: string }[] = [
    { key: "customer_id", label: "Customer ID" },
    { key: "memory_count", label: "Memories" },
    { key: "last_activity", label: "Last activity" },
  ];

  return (
    <div className="space-y-3">
      <div className="relative max-w-sm">
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
          placeholder="Filter by customer ID…"
          value={filter}
          onChange={(e) => {
            setFilter(e.target.value);
            setPage(0);
          }}
        />
      </div>
      {filtered.length === 0 ? (
        <EmptyState>No customers match.</EmptyState>
      ) : (
        <div className="overflow-hidden rounded-2xl border border-[var(--color-border)] bg-white shadow-sm">
          <div className="max-h-[70vh] overflow-auto">
            <table className="w-full text-sm">
              <thead className="sticky top-0 z-10 bg-slate-50 text-left text-xs uppercase tracking-wide text-[var(--color-muted)]">
                <tr>
                  {columns.map((col) => (
                    <th key={col.key} className="px-4 py-3 font-medium">
                      <button
                        type="button"
                        onClick={() => toggleSort(col.key)}
                        className="inline-flex items-center gap-1 transition-colors hover:text-[var(--color-text)]"
                      >
                        {col.label}
                        {sortKey === col.key && <span>{sortDir === "asc" ? "↑" : "↓"}</span>}
                      </button>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--color-border)]">
                {pageItems.map((c) => (
                  <tr key={c.customer_id} className="transition-colors hover:bg-slate-50">
                    <td className="px-4 py-3">
                      <Link
                        href={`/browse/${encodeURIComponent(c.customer_id)}`}
                        className="font-medium text-[var(--color-text)] underline decoration-slate-300 underline-offset-2 transition-colors hover:text-[var(--color-primary)] hover:decoration-[var(--color-primary)]"
                      >
                        {c.customer_id}
                      </Link>
                    </td>
                    <td className="px-4 py-3 text-[var(--color-muted)]">{c.memory_count}</td>
                    <td className="px-4 py-3 text-[var(--color-muted)]">
                      {new Date(c.last_activity).toLocaleString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <Pagination page={safePage} pageCount={pageCount} onChange={setPage} />
    </div>
  );
}
