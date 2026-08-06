import { PageHeader } from "@/components/features/page-header";
import { Reveal } from "@/components/features/reveal";
import { Card, CardContent } from "@/components/ui/card";
import { StatusBadge } from "@/components/ui/badge";
import { EmptyState } from "@/components/features/empty-state";
import { paymentProviders } from "@/data/report";
import { CreditCard } from "lucide-react";

export default function PaymentsPage() {
  return (
    <div>
      <PageHeader
        eyebrow="10 · Payment integrations"
        title="No payment provider integration"
        description="This repo is a governed memory API and console — there is no payments module, no checkout flow, and no provider SDK anywhere in api/, core/, web/, or this dashboard."
      />

      <Reveal index={0}>
        <EmptyState
          icon={CreditCard}
          title="Not found"
          description="Searched api/, core/, web/, sdk/, and integrations/ for any payment-provider client — none exists."
        />
      </Reveal>

      <div className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
        {paymentProviders.map((p, i) => (
          <Reveal index={i} key={p.name}>
            <Card className="h-full">
              <CardContent className="p-4">
                <div className="flex items-center justify-between gap-2">
                  <p className="text-[14px] font-semibold text-ink">{p.name}</p>
                  <StatusBadge status={p.status} />
                </div>
                <p className="mt-2 text-[12.5px] leading-relaxed text-ink-dim">{p.note}</p>
              </CardContent>
            </Card>
          </Reveal>
        ))}
      </div>
    </div>
  );
}
