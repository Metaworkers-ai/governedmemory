"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import { PanelLeftClose, PanelLeftOpen, ShieldCheck } from "lucide-react";
import { NavList } from "./nav-list";
import { repoMeta, repoScore } from "@/data/report";
import { cn } from "@/lib/utils";

export function Sidebar() {
  const [collapsed, setCollapsed] = useState(false);

  return (
    <motion.aside
      animate={{ width: collapsed ? 68 : 248 }}
      transition={{ type: "spring", stiffness: 320, damping: 32 }}
      className="sticky top-0 hidden h-svh shrink-0 flex-col border-r border-border bg-bg-elevated md:flex"
    >
      <div className={cn("flex h-14 items-center gap-2 border-b border-border px-4", collapsed && "justify-center px-0")}>
        <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-accent text-accent-ink">
          <ShieldCheck className="h-4 w-4" strokeWidth={2} />
        </div>
        {!collapsed && (
          <div className="min-w-0 leading-tight">
            <p className="truncate text-[13px] font-semibold text-ink">{repoMeta.name}</p>
            <p className="truncate font-mono text-[10.5px] text-ink-faint">audit · score {repoScore}</p>
          </div>
        )}
      </div>

      <div className="flex-1 py-2">
        <NavList collapsed={collapsed} />
      </div>

      <div className="border-t border-border p-2">
        <button
          onClick={() => setCollapsed((c) => !c)}
          className="flex w-full items-center justify-center gap-2 rounded-lg py-2 text-ink-dim transition-colors hover:bg-bg-sunken hover:text-ink focus-ring"
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          {collapsed ? <PanelLeftOpen className="h-4 w-4" /> : <PanelLeftClose className="h-4 w-4" />}
          {!collapsed && <span className="text-[12.5px]">Collapse</span>}
        </button>
      </div>
    </motion.aside>
  );
}
