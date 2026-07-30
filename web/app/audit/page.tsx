import { AuditTable } from "@/components/AuditTable";
import { EmptyState, PageHeader } from "@/components/ui";
import { listAudit } from "@/lib/backend";

export const dynamic = "force-dynamic";

export default async function AuditPage() {
  const events = await listAudit(50);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Audit trail"
        description="Each event's hash is SHA-256(prev_hash + payload) — a tamper-evident chain."
      />

      {events.length === 0 ? <EmptyState>No audit events yet.</EmptyState> : <AuditTable events={events} />}
    </div>
  );
}
