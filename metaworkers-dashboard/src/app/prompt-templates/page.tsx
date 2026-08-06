import { PageHeader } from "@/components/features/page-header";
import { Reveal } from "@/components/features/reveal";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/features/empty-state";
import { promptTemplates } from "@/data/report";
import { MessagesSquare } from "lucide-react";

export default function PromptTemplatesPage() {
  return (
    <div>
      <PageHeader
        eyebrow="12 · Prompt templates"
        title="No prompt templates in this repo"
        description="GovernedMemory has no LLM chat/completion call site and no prompts/ directory or template engine — the OpenAI/Cohere SDKs here are used only for embeddings (see AI Analysis)."
      />

      {promptTemplates.length === 0 && (
        <Reveal index={0}>
          <EmptyState
            icon={MessagesSquare}
            title="Not found"
            description="Searched api/, core/, sdk/, and integrations/ for a system prompt or template file — none exists."
          />
        </Reveal>
      )}

      {promptTemplates.map((p, i) => (
        <Reveal index={i} key={p.file}>
          <Card>
            <CardHeader>
              <div className="flex items-center gap-2">
                <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-accent-soft text-accent">
                  <MessagesSquare className="h-4 w-4" />
                </div>
                <div>
                  <CardTitle className="font-mono text-[12.5px]">{p.file}</CardTitle>
                </div>
              </div>
            </CardHeader>
            <CardContent>
              <CardDescription className="mb-4">{p.purpose}</CardDescription>
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                <div>
                  <p className="mb-1 text-[11px] font-medium uppercase tracking-wide text-ink-faint">Model</p>
                  <Badge tone="neutral">{p.model}</Badge>
                </div>
                <div>
                  <p className="mb-1 text-[11px] font-medium uppercase tracking-wide text-ink-faint">Used by</p>
                  <p className="font-mono text-[12px] text-ink-dim">{p.usedBy}</p>
                </div>
              </div>
              {p.intents && (
                <div className="mt-4">
                  <p className="mb-1.5 text-[11px] font-medium uppercase tracking-wide text-ink-faint">Intent taxonomy ({p.intents.length})</p>
                  <div className="flex flex-wrap gap-1.5">
                    {p.intents.map((intent) => (
                      <Badge key={intent} tone="outline">
                        {intent}
                      </Badge>
                    ))}
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        </Reveal>
      ))}
    </div>
  );
}
