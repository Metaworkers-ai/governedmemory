import { CustomerTable } from "@/components/CustomerTable";
import { EmptyState, PageHeader } from "@/components/ui";
import { listCustomers } from "@/lib/backend";

export const dynamic = "force-dynamic";

export default async function BrowsePage() {
  const customers = await listCustomers();

  return (
    <div className="space-y-6">
      <PageHeader
        title="Browse customers"
        description="Everyone with at least one memory recorded for this tenant."
      />
      {customers.length === 0 ? (
        <EmptyState>No customers yet — write a memory to get started.</EmptyState>
      ) : (
        <CustomerTable customers={customers} />
      )}
    </div>
  );
}
