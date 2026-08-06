import { PageHeader } from "@/components/features/page-header";
import { Reveal } from "@/components/features/reveal";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { StatusBadge } from "@/components/ui/badge";
import { authMechanisms } from "@/data/report";
import { ShieldCheck } from "lucide-react";

export default function AuthenticationPage() {
  return (
    <div>
      <PageHeader
        eyebrow="09 · Authentication"
        title="Per-tenant API key, not end-user login"
        description="No user-account system exists. “Auth” here means a single static Bearer API key per tenant, resolved server-side and never accepted from the client (api/auth.py)."
      />

      <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
        {authMechanisms.map((m, i) => (
          <Reveal index={i} key={m.name}>
            <Card>
              <CardHeader className="pb-2">
                <div className="flex items-start justify-between gap-2">
                  <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-accent-soft text-accent">
                    <ShieldCheck className="h-4 w-4" />
                  </div>
                  <StatusBadge status={m.status} />
                </div>
              </CardHeader>
              <CardContent>
                <CardTitle className="mb-1">{m.name}</CardTitle>
                <p className="font-mono text-[11px] text-ink-faint">{m.file}</p>
                <CardDescription className="mt-2">{m.note}</CardDescription>
              </CardContent>
            </Card>
          </Reveal>
        ))}
      </div>
    </div>
  );
}
