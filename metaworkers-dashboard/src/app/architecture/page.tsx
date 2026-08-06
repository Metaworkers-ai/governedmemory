import { PageHeader } from "@/components/features/page-header";
import { Reveal } from "@/components/features/reveal";
import { ArchitectureFlow } from "@/components/features/architecture-flow";
import { Card } from "@/components/ui/card";

export default function ArchitecturePage() {
  return (
    <div>
      <PageHeader
        eyebrow="15 · Architecture"
        title="Interactive system map"
        description="Both Next.js consoles call the FastAPI surface directly. A write passes through the write-governor's dedup/injection scan and an embedding provider before MemoryStore persists it; reads go through the retrieval + policy engines. Every operation lands in the hash-chained audit log. Drag to pan, scroll to zoom."
      />
      <Reveal index={0}>
        <ArchitectureFlow />
      </Reveal>
      <Reveal index={1} className="mt-4">
        <Card className="flex flex-wrap gap-4 p-4 text-[12px] text-ink-dim">
          <Legend color="var(--accent)" label="Frontend / governance step" />
          <Legend color="var(--ink-faint)" label="Backend / store" />
          <Legend color="var(--info)" label="AI (embeddings)" />
          <Legend color="var(--warn)" label="Database" />
        </Card>
      </Reveal>
    </div>
  );
}

function Legend({ color, label }: { color: string; label: string }) {
  return (
    <span className="flex items-center gap-1.5">
      <span className="h-2.5 w-2.5 rounded-full" style={{ background: color }} />
      {label}
    </span>
  );
}
