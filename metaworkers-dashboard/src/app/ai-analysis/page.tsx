import { PageHeader } from "@/components/features/page-header";
import { FlowSteps } from "@/components/features/flow-steps";
import { Reveal } from "@/components/features/reveal";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { aiProviders, aiNotFound, aiFlow, promptTemplates } from "@/data/report";
import { Sparkles, FileCode2 } from "lucide-react";

export default function AiAnalysisPage() {
  return (
    <div>
      <PageHeader
        eyebrow="02 · AI analysis"
        title="Embeddings only, no chat/completion calls"
        description="AI usage here is a three-tier embedding fallback chain for semantic search — there is no LLM chat, completion, or agent call site anywhere in api/ or core/."
      />

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
        {aiProviders.map((p, i) => (
          <Reveal index={i} key={p.provider} className="xl:col-span-1">
            <Card className="h-full">
              <CardHeader>
                <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-accent-soft text-accent">
                  <Sparkles className="h-4.5 w-4.5" />
                </div>
                <CardTitle className="mt-2 text-base">{p.provider}</CardTitle>
                <CardDescription>{p.purpose}</CardDescription>
              </CardHeader>
              <CardContent className="flex flex-col gap-2.5 text-[13px]">
                <Row label="SDK" value={p.sdk} mono />
                <Row label="Model" value={p.model} mono />
                <Row label="File" value={p.file} mono />
                <Row label="References" value={String(p.referenceCount)} />
              </CardContent>
            </Card>
          </Reveal>
        ))}

        <Reveal index={1} className="xl:col-span-2">
          <Card className="h-full">
            <CardHeader>
              <CardTitle>Execution flow</CardTitle>
              <CardDescription>How an inbound message becomes a routed worker action.</CardDescription>
            </CardHeader>
            <CardContent>
              <FlowSteps steps={aiFlow} />
            </CardContent>
          </Card>
        </Reveal>
      </div>

      {promptTemplates.length > 0 && (
        <Reveal index={2} className="mt-4">
          <Card>
            <CardHeader>
              <div className="flex items-center gap-2">
                <FileCode2 className="h-4 w-4 text-accent" />
                <CardTitle>Prompt in use</CardTitle>
              </div>
              <CardDescription>{promptTemplates[0]?.file}</CardDescription>
            </CardHeader>
            <CardContent>
              <p className="mb-3 text-[13px] text-ink-dim">{promptTemplates[0]?.purpose}</p>
              <div className="flex flex-wrap gap-1.5">
                {promptTemplates[0]?.intents?.map((intent) => (
                  <Badge key={intent} tone="neutral">
                    {intent}
                  </Badge>
                ))}
              </div>
            </CardContent>
          </Card>
        </Reveal>
      )}

      <Reveal index={3} className="mt-4">
        <Card>
          <CardHeader>
            <CardTitle>Providers not found</CardTitle>
            <CardDescription>Searched for across src/, web/, requirements.txt, and package.json — no evidence found on this branch.</CardDescription>
          </CardHeader>
          <CardContent className="flex flex-wrap gap-1.5">
            {aiNotFound.map((name) => (
              <Badge key={name} tone="outline">
                {name}
              </Badge>
            ))}
          </CardContent>
        </Card>
      </Reveal>
    </div>
  );
}

function Row({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="flex items-start justify-between gap-3 border-t border-border-soft pt-2.5 first:border-0 first:pt-0">
      <span className="shrink-0 text-ink-faint">{label}</span>
      <span className={`text-right text-ink ${mono ? "font-mono text-[12px]" : ""}`}>{value}</span>
    </div>
  );
}
