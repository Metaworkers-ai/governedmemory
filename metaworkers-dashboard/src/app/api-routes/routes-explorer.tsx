"use client";

import { useMemo, useState } from "react";
import { Card } from "@/components/ui/card";
import { Badge, StatusBadge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Sheet, SheetContent, SheetTitle, SheetDescription } from "@/components/ui/sheet";
import type { ApiRoute } from "@/types/report";
import { Search, ChevronRight } from "lucide-react";
import { cn } from "@/lib/utils";

const methodTone: Record<string, string> = {
  GET: "text-info bg-info-bg border-info-border",
  POST: "text-good bg-good-bg border-good-border",
  PUT: "text-warn bg-warn-bg border-warn-border",
  DELETE: "text-crit bg-crit-bg border-crit-border",
};

export function RoutesExplorer({ routes }: { routes: ApiRoute[] }) {
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState<ApiRoute | null>(null);

  const filtered = useMemo(() => {
    const q = query.toLowerCase().trim();
    if (!q) return routes;
    return routes.filter(
      (r) => r.route.toLowerCase().includes(q) || r.module.toLowerCase().includes(q) || r.purpose.toLowerCase().includes(q)
    );
  }, [routes, query]);

  return (
    <div>
      <div className="mb-3 flex justify-end">
        <div className="relative w-56">
          <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-ink-faint" />
          <Input placeholder="Search routes…" value={query} onChange={(e) => setQuery(e.target.value)} className="pl-8" />
        </div>
      </div>

      <Card className="overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[640px] text-left text-[13px]">
            <thead>
              <tr className="border-b border-border bg-bg-sunken text-[11px] uppercase tracking-wide text-ink-faint">
                <th className="px-4 py-2.5 font-medium">Method</th>
                <th className="px-4 py-2.5 font-medium">Route</th>
                <th className="px-4 py-2.5 font-medium">Module</th>
                <th className="px-4 py-2.5 font-medium">Purpose</th>
                <th className="px-4 py-2.5 font-medium">Auth</th>
                <th className="px-4 py-2.5 font-medium">Status</th>
                <th className="w-8"></th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((r) => (
                <tr
                  key={r.route + r.method}
                  onClick={() => setSelected(r)}
                  className="cursor-pointer border-b border-border-soft transition-colors last:border-0 hover:bg-bg-sunken"
                >
                  <td className="px-4 py-2.5">
                    <span className={cn("rounded border px-1.5 py-0.5 font-mono text-[10.5px] font-semibold", methodTone[r.method])}>
                      {r.method}
                    </span>
                  </td>
                  <td className="px-4 py-2.5 font-mono text-[12.5px] text-ink">{r.route}</td>
                  <td className="px-4 py-2.5 font-mono text-[11.5px] text-ink-faint">{r.module}</td>
                  <td className="px-4 py-2.5 text-ink-dim">{r.purpose}</td>
                  <td className="px-4 py-2.5">
                    <Badge tone={r.authRequired ? "warn" : "outline"}>{r.authRequired ? "Required" : "None"}</Badge>
                  </td>
                  <td className="px-4 py-2.5">
                    <StatusBadge status={r.status} />
                  </td>
                  <td className="px-2 py-2.5 text-ink-faint">
                    <ChevronRight className="h-4 w-4" />
                  </td>
                </tr>
              ))}
              {filtered.length === 0 && (
                <tr>
                  <td colSpan={7} className="px-4 py-10 text-center text-ink-faint">
                    No routes match &quot;{query}&quot;.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </Card>

      <Sheet open={!!selected} onOpenChange={(o) => !o && setSelected(null)}>
        <SheetContent>
          {selected && (
            <div className="flex flex-col gap-5">
              <div>
                <span className={cn("mb-2 inline-block rounded border px-1.5 py-0.5 font-mono text-[10.5px] font-semibold", methodTone[selected.method])}>
                  {selected.method}
                </span>
                <SheetTitle className="font-mono text-[16px] font-semibold text-ink">{selected.route}</SheetTitle>
                <SheetDescription className="mt-1 text-[13px] text-ink-dim">{selected.purpose}</SheetDescription>
              </div>

              <Detail label="Description" value={selected.description} />
              {selected.request && <Detail label="Request" value={selected.request} mono />}
              {selected.response && <Detail label="Response" value={selected.response} mono />}

              <div>
                <p className="mb-1.5 text-[11px] font-medium uppercase tracking-wide text-ink-faint">Authentication</p>
                <Badge tone={selected.authRequired ? "warn" : "outline"}>{selected.authRequired ? "Required" : "Not required"}</Badge>
              </div>

              {selected.dependencies && (
                <div>
                  <p className="mb-1.5 text-[11px] font-medium uppercase tracking-wide text-ink-faint">Dependencies</p>
                  <div className="flex flex-col gap-1">
                    {selected.dependencies.map((d) => (
                      <span key={d} className="rounded border border-border-soft bg-bg-sunken px-2 py-1 font-mono text-[11.5px] text-ink-dim">
                        {d}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              <div>
                <p className="mb-1.5 text-[11px] font-medium uppercase tracking-wide text-ink-faint">Status</p>
                <StatusBadge status={selected.status} />
              </div>
            </div>
          )}
        </SheetContent>
      </Sheet>
    </div>
  );
}

function Detail({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div>
      <p className="mb-1.5 text-[11px] font-medium uppercase tracking-wide text-ink-faint">{label}</p>
      <p className={cn("text-[13px] text-ink", mono && "font-mono text-[12.5px] text-ink-dim")}>{value}</p>
    </div>
  );
}
