import { PageHeader } from "@/components/features/page-header";
import { FlowSteps } from "@/components/features/flow-steps";
import { Reveal } from "@/components/features/reveal";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { EmptyState } from "@/components/features/empty-state";
import { agentFrameworkFlow, workers, agentFrameworkNote } from "@/data/report";
import { Bot } from "lucide-react";

export default function AgentFrameworkPage() {
  return (
    <div>
      <PageHeader
        eyebrow="13 · Agent framework"
        title="Memory infrastructure, not an agent framework"
        description="LangChain, CrewAI, LlamaIndex, AutoGen, Semantic Kernel, and the OpenAI Agents SDK were all searched for and not found — this repo governs memory for external agents rather than running any itself."
      />

      <Reveal index={0}>
        <Card>
          <CardHeader>
            <CardTitle>External-write governance flow</CardTitle>
            <CardDescription>How a memory proposed by an external agent (e.g. via the Mem0 adapter) becomes trusted.</CardDescription>
          </CardHeader>
          <CardContent>
            <FlowSteps steps={agentFrameworkFlow} />
          </CardContent>
        </Card>
      </Reveal>

      {workers.length === 0 && (
        <Reveal index={1} className="mt-4">
          <EmptyState
            icon={Bot}
            title="No worker/task-queue concept"
            description="No task queue, worker registry, or lease-and-run runtime exists in api/ or core/ — governance runs synchronously inside each request."
          />
        </Reveal>
      )}

      <div className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-2">
        {workers.map((w, i) => (
          <Reveal index={i} key={w.name}>
            <Card>
              <CardContent className="flex items-start gap-3 p-4">
                <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-accent-soft text-accent">
                  <Bot className="h-4.5 w-4.5" />
                </div>
                <div>
                  <p className="text-[13.5px] font-semibold text-ink">{w.name}</p>
                  <p className="mt-1 text-[12.5px] text-ink-dim">{w.description}</p>
                  <p className="mt-1.5 font-mono text-[11px] text-ink-faint">{w.file}</p>
                </div>
              </CardContent>
            </Card>
          </Reveal>
        ))}
      </div>

      <Reveal index={2} className="mt-4">
        <Card className="p-4">
          <p className="text-[13px] leading-relaxed text-ink-dim">{agentFrameworkNote}</p>
        </Card>
      </Reveal>
    </div>
  );
}
