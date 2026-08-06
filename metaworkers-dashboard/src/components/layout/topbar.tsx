"use client";

import { useState } from "react";
import { usePathname } from "next/navigation";
import { Menu, Moon, Sun, GitBranch } from "lucide-react";
import { Sheet, SheetContent, SheetTitle } from "@/components/ui/sheet";
import { NavList } from "./nav-list";
import { useTheme } from "@/hooks/use-theme";
import { repoMeta } from "@/data/report";
import { navGroups } from "@/lib/nav";
import { Badge } from "@/components/ui/badge";

function currentLabel(pathname: string) {
  for (const group of navGroups) {
    for (const item of group.items) {
      if (item.href === pathname) return item.label;
    }
  }
  return "Dashboard";
}

export function Topbar() {
  const { isDark, toggle } = useTheme();
  const [open, setOpen] = useState(false);
  const pathname = usePathname();

  return (
    <header className="sticky top-0 z-30 flex h-14 items-center gap-3 border-b border-border bg-bg-elevated/80 px-4 backdrop-blur-md md:px-6">
      <Sheet open={open} onOpenChange={setOpen}>
        <button
          className="flex h-9 w-9 items-center justify-center rounded-lg text-ink-dim hover:bg-bg-sunken md:hidden focus-ring"
          onClick={() => setOpen(true)}
          aria-label="Open navigation"
        >
          <Menu className="h-5 w-5" />
        </button>
        <SheetContent className="max-w-[280px] p-0">
          <SheetTitle className="sr-only">Navigation</SheetTitle>
          <div className="border-b border-border px-4 py-4 text-sm font-semibold">{repoMeta.name}</div>
          <NavList onNavigate={() => setOpen(false)} />
        </SheetContent>
      </Sheet>

      <div className="flex min-w-0 flex-1 items-center gap-2">
        <h1 className="truncate text-[14.5px] font-semibold text-ink">{currentLabel(pathname)}</h1>
        <span className="hidden items-center gap-1.5 font-mono text-[11.5px] text-ink-faint sm:flex">
          <GitBranch className="h-3.5 w-3.5" />
          {repoMeta.branch}
        </span>
      </div>

      <Badge tone="outline" className="hidden sm:inline-flex">
        {repoMeta.commit}
      </Badge>

      <button
        onClick={toggle}
        className="flex h-9 w-9 items-center justify-center rounded-lg text-ink-dim transition-colors hover:bg-bg-sunken hover:text-ink focus-ring"
        aria-label="Toggle theme"
      >
        {isDark ? <Sun className="h-[17px] w-[17px]" /> : <Moon className="h-[17px] w-[17px]" />}
      </button>
    </header>
  );
}
