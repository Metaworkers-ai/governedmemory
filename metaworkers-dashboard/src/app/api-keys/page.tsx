import { PageHeader } from "@/components/features/page-header";
import { Reveal } from "@/components/features/reveal";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { apiKeys } from "@/data/report";
import { ShieldCheck, ShieldX } from "lucide-react";

export default function ApiKeysPage() {
  const detected = apiKeys.length;
  const used = apiKeys.filter((k) => k.used).length;
  const undocumented = apiKeys.filter((k) => !k.documented).length;

  return (
    <div>
      <PageHeader
        eyebrow="07 · API keys"
        title="Names only — never values"
        description="Every credential-shaped variable found in code or .env.example, with whether it's documented and whether it's actually consumed."
      />

      <div className="mb-4 grid grid-cols-3 gap-3">
        <Card className="p-4">
          <p className="text-[11px] uppercase tracking-wide text-ink-faint">Detected</p>
          <p className="mt-1 font-mono text-xl font-semibold text-ink">{detected}</p>
        </Card>
        <Card className="p-4">
          <p className="text-[11px] uppercase tracking-wide text-ink-faint">Used</p>
          <p className="mt-1 font-mono text-xl font-semibold text-good">{used}</p>
        </Card>
        <Card className="p-4">
          <p className="text-[11px] uppercase tracking-wide text-ink-faint">Undocumented</p>
          <p className="mt-1 font-mono text-xl font-semibold text-warn">{undocumented}</p>
        </Card>
      </div>

      <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
        {apiKeys.map((k, i) => (
          <Reveal index={i} key={k.name}>
            <Card>
              <CardContent className="flex items-start justify-between gap-3 p-4">
                <div className="min-w-0">
                  <p className="truncate font-mono text-[13px] font-medium text-ink">{k.name}</p>
                  <p className="mt-1 font-mono text-[11px] text-ink-faint">{k.file}</p>
                </div>
                <div className="flex shrink-0 flex-col items-end gap-1.5">
                  <Badge tone={k.used ? "good" : "warn"}>
                    {k.used ? <ShieldCheck className="h-3 w-3" /> : <ShieldX className="h-3 w-3" />}
                    {k.used ? "Used" : "Unused"}
                  </Badge>
                  <Badge tone={k.documented ? "outline" : "crit"}>{k.documented ? "✓ documented" : "✗ undocumented"}</Badge>
                </div>
              </CardContent>
            </Card>
          </Reveal>
        ))}
      </div>

      <Reveal index={apiKeys.length} className="mt-4">
        <Card>
          <CardHeader>
            <CardTitle>Not found anywhere</CardTitle>
            <CardDescription>Searched for and absent: JWT_SECRET, AUTH_SECRET, PRIVATE_KEY, PUBLIC_KEY.</CardDescription>
          </CardHeader>
        </Card>
      </Reveal>
    </div>
  );
}
