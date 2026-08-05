import Link from "next/link";

import { MemoryList } from "@/components/MemoryList";
import { listMemoriesForCustomer } from "@/lib/backend";

export const dynamic = "force-dynamic";

export default async function CustomerMemoriesPage({
  params,
}: {
  params: Promise<{ customerId: string }>;
}) {
  const { customerId } = await params;
  const memories = await listMemoriesForCustomer(customerId);

  return (
    <div className="space-y-6">
      <div>
        <Link
          href="/browse"
          className="inline-flex items-center gap-1 text-sm text-[var(--color-muted)] transition-colors hover:text-[var(--color-text)]"
        >
          ← Back to customers
        </Link>
        <h1 className="mt-2 text-2xl font-semibold tracking-tight text-[var(--color-text)]">
          Memories for <code className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-lg">{customerId}</code>
        </h1>
        <p className="mt-1 text-sm text-[var(--color-muted)]">{memories.length} memory record(s).</p>
      </div>
      <MemoryList memories={memories} />
    </div>
  );
}
