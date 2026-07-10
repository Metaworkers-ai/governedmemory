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
    <div className="space-y-4">
      <div>
        <Link href="/browse" className="text-sm text-neutral-500 hover:text-neutral-900">
          ← Back to customers
        </Link>
        <h1 className="mt-1 text-lg font-semibold text-neutral-900">
          Memories for <code className="font-mono">{customerId}</code>
        </h1>
        <p className="mt-1 text-sm text-neutral-600">{memories.length} memory record(s).</p>
      </div>
      <MemoryList memories={memories} />
    </div>
  );
}
