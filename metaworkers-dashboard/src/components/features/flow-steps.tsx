"use client";

import { ArrowRight, ArrowDown } from "lucide-react";
import { motion } from "framer-motion";
import { Reveal } from "./reveal";

export function FlowSteps({
  steps,
  direction = "horizontal",
}: {
  steps: { label: string; detail: string }[];
  direction?: "horizontal" | "vertical";
}) {
  const horizontal = direction === "horizontal";
  return (
    <div
      className={
        horizontal
          ? "flex flex-col gap-3 overflow-x-auto pb-2 md:flex-row md:items-stretch md:gap-0"
          : "flex flex-col gap-0"
      }
    >
      {steps.map((step, i) => (
        <div key={step.label} className={horizontal ? "flex items-center md:items-stretch" : "flex flex-col"}>
          <Reveal index={i} className={horizontal ? "w-full md:w-56" : "w-full"}>
            <div className="flex h-full flex-col justify-center rounded-[var(--radius)] border border-border bg-bg-elevated px-4 py-3.5 shadow-[var(--shadow-sm)]">
              <p className="font-mono text-[10px] uppercase tracking-wide text-accent">Step {i + 1}</p>
              <p className="mt-0.5 text-[13.5px] font-semibold text-ink">{step.label}</p>
              <p className="mt-1 text-[12px] leading-snug text-ink-dim">{step.detail}</p>
            </div>
          </Reveal>
          {i < steps.length - 1 && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: i * 0.035 + 0.15 }}
              className={
                horizontal
                  ? "flex shrink-0 items-center justify-center px-2 text-ink-faint md:px-3"
                  : "flex items-center justify-center py-1.5 text-ink-faint"
              }
            >
              {horizontal ? <ArrowRight className="h-4 w-4 md:hidden" /> : null}
              {horizontal ? <ArrowRight className="hidden h-4 w-4 md:block" /> : <ArrowDown className="h-4 w-4" />}
            </motion.div>
          )}
        </div>
      ))}
    </div>
  );
}
