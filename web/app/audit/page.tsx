import { EmptyState, OutcomeBadge } from "@/components/ui";
import { listAudit } from "@/lib/backend";

export const dynamic = "force-dynamic";

export default async function AuditPage() {
  const events = await listAudit(50);

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-lg font-semibold text-neutral-900">Audit trail</h1>
        <p className="mt-1 text-sm text-neutral-600">
          Each event&apos;s hash is SHA-256(prev_hash + payload) — a tamper-evident chain.
        </p>
      </div>

      {events.length === 0 ? (
        <EmptyState>No audit events yet.</EmptyState>
      ) : (
        <div className="overflow-x-auto rounded-lg border border-neutral-200 bg-white">
          <table className="w-full text-sm">
            <thead className="bg-neutral-50 text-left text-xs uppercase tracking-wide text-neutral-500">
              <tr>
                <th className="px-3 py-2 font-medium">Time</th>
                <th className="px-3 py-2 font-medium">Op</th>
                <th className="px-3 py-2 font-medium">Outcome</th>
                <th className="px-3 py-2 font-medium">Agent / Session</th>
                <th className="px-3 py-2 font-medium">Hash</th>
                <th className="px-3 py-2 font-medium">Prev hash</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-neutral-100">
              {events.map((e) => (
                <tr key={e.id}>
                  <td className="whitespace-nowrap px-3 py-2 text-neutral-600">
                    {new Date(e.ts).toLocaleString()}
                  </td>
                  <td className="px-3 py-2 font-medium text-neutral-800">{e.op}</td>
                  <td className="px-3 py-2">
                    <OutcomeBadge outcome={e.outcome} />
                  </td>
                  <td className="px-3 py-2 text-neutral-600">
                    {e.agent_id} / {e.session_id}
                  </td>
                  <td className="px-3 py-2 font-mono text-xs text-neutral-500">{e.hash.slice(0, 12)}…</td>
                  <td className="px-3 py-2 font-mono text-xs text-neutral-500">
                    {e.prev_hash.slice(0, 12)}…
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
