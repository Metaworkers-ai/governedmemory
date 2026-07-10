import { CustomerTable } from "@/components/CustomerTable";
import { EmptyState } from "@/components/ui";
import { listCustomers } from "@/lib/backend";

export const dynamic = "force-dynamic";

export default async function BrowsePage() {
  const customers = await listCustomers();

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-lg font-semibold text-neutral-900">Browse customers</h1>
        <p className="mt-1 text-sm text-neutral-600">
          Everyone with at least one memory recorded for this tenant.
        </p>
      </div>
      {customers.length === 0 ? (
        <EmptyState>No customers yet — write a memory to get started.</EmptyState>
      ) : (
        <CustomerTable customers={customers} />
      )}
    </div>
  );
}
