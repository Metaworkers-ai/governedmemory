"use client";

import Link from "next/link";
import { useState } from "react";

import { EmptyState, Input } from "@/components/ui";
import type { CustomerSummary } from "@/lib/types";

export function CustomerTable({ customers }: { customers: CustomerSummary[] }) {
  const [filter, setFilter] = useState("");

  const filtered = filter
    ? customers.filter((c) => c.customer_id.toLowerCase().includes(filter.toLowerCase()))
    : customers;

  return (
    <div className="space-y-3">
      <Input
        placeholder="Filter by customer ID…"
        value={filter}
        onChange={(e) => setFilter(e.target.value)}
      />
      {filtered.length === 0 ? (
        <EmptyState>No customers match.</EmptyState>
      ) : (
        <div className="overflow-hidden rounded-lg border border-neutral-200">
          <table className="w-full text-sm">
            <thead className="bg-neutral-50 text-left text-xs uppercase tracking-wide text-neutral-500">
              <tr>
                <th className="px-4 py-2 font-medium">Customer ID</th>
                <th className="px-4 py-2 font-medium">Memories</th>
                <th className="px-4 py-2 font-medium">Last activity</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-neutral-100">
              {filtered.map((c) => (
                <tr key={c.customer_id} className="hover:bg-neutral-50">
                  <td className="px-4 py-2">
                    <Link
                      href={`/browse/${encodeURIComponent(c.customer_id)}`}
                      className="font-medium text-neutral-900 underline decoration-neutral-300 underline-offset-2 hover:decoration-neutral-900"
                    >
                      {c.customer_id}
                    </Link>
                  </td>
                  <td className="px-4 py-2 text-neutral-600">{c.memory_count}</td>
                  <td className="px-4 py-2 text-neutral-600">
                    {new Date(c.last_activity).toLocaleString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
