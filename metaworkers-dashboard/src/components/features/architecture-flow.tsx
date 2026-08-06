"use client";

import { useMemo } from "react";
import ReactFlow, {
  Background,
  Controls,
  MiniMap,
  Handle,
  Position,
  BackgroundVariant,
  type Node,
  type Edge,
  type NodeProps,
} from "reactflow";
import "reactflow/dist/style.css";
import { architectureNodes, architectureEdges } from "@/data/report";
import type { ArchitectureNodeData } from "@/types/report";
import { cn } from "@/lib/utils";

const positions: Record<string, { x: number; y: number }> = {
  web: { x: 20, y: 40 },
  dashboard: { x: 20, y: 160 },
  api: { x: 360, y: 100 },
  governor: { x: 700, y: 20 },
  embed: { x: 1040, y: 20 },
  store: { x: 700, y: 200 },
  retrieval: { x: 700, y: 360 },
  audit: { x: 700, y: 500 },
  db: { x: 1040, y: 380 },
};

const kindStyle: Record<ArchitectureNodeData["kind"], string> = {
  frontend: "border-accent/50 bg-accent-soft",
  backend: "border-border bg-bg-elevated",
  ai: "border-info-border bg-info-bg",
  queue: "border-border bg-bg-elevated",
  worker: "border-accent/50 bg-accent-soft",
  connector: "border-border bg-bg-sunken",
  payment: "border-good-border bg-good-bg",
  messaging: "border-info-border bg-info-bg",
  database: "border-warn-border bg-warn-bg",
};

function ArchNode({ data }: NodeProps<ArchitectureNodeData & { dashed?: boolean }>) {
  return (
    <div
      className={cn(
        "w-[210px] rounded-[10px] border px-3.5 py-2.5 shadow-[var(--shadow-sm)]",
        kindStyle[data.kind],
        data.dashed && "border-dashed opacity-70"
      )}
    >
      <Handle type="target" position={Position.Left} className="!bg-ink-faint !border-0 !h-1.5 !w-1.5" />
      <p className="truncate text-[12.5px] font-semibold text-ink">{data.label}</p>
      <p className="mt-0.5 truncate text-[10.5px] text-ink-dim">{data.sub}</p>
      <Handle type="source" position={Position.Right} className="!bg-ink-faint !border-0 !h-1.5 !w-1.5" />
    </div>
  );
}

const nodeTypes = { arch: ArchNode };

export function ArchitectureFlow() {
  const nodes: Node[] = useMemo(
    () =>
      architectureNodes.map((n) => ({
        id: n.id,
        type: "arch",
        position: positions[n.id] ?? { x: 0, y: 0 },
        data: n,
      })),
    []
  );

  const edges: Edge[] = useMemo(
    () =>
      architectureEdges.map((e, i) => ({
        id: `e-${i}`,
        source: e.source,
        target: e.target,
        animated: e.animated,
        style: {
          stroke: "var(--ink-faint)",
          strokeWidth: 1.4,
          strokeDasharray: e.dashed ? "4 4" : undefined,
        },
      })),
    []
  );

  return (
    <div className="h-[600px] w-full overflow-hidden rounded-[var(--radius)] border border-border bg-bg-sunken">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        fitView
        fitViewOptions={{ padding: 0.15 }}
        minZoom={0.4}
        maxZoom={1.5}
        proOptions={{ hideAttribution: true }}
      >
        <Background variant={BackgroundVariant.Dots} gap={18} size={1} color="var(--border)" />
        <Controls showInteractive={false} className="!shadow-[var(--shadow-md)] [&>button]:!border-border [&>button]:!bg-bg-elevated [&>button]:!fill-ink" />
        <MiniMap
          pannable
          zoomable
          maskColor="rgba(0,0,0,0.35)"
          className="!border !border-border !bg-bg-elevated"
          nodeColor="var(--border)"
        />
      </ReactFlow>
    </div>
  );
}
