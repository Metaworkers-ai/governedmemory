"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { navGroups } from "@/lib/nav";
import { cn } from "@/lib/utils";

export function NavList({ collapsed = false, onNavigate }: { collapsed?: boolean; onNavigate?: () => void }) {
  const pathname = usePathname();

  return (
    <nav className="flex flex-col gap-5 overflow-y-auto px-3 py-2">
      {navGroups.map((group) => (
        <div key={group.title} className="flex flex-col gap-1">
          {!collapsed && (
            <p className="px-2.5 pb-1 text-[10.5px] font-semibold uppercase tracking-[0.08em] text-ink-faint">
              {group.title}
            </p>
          )}
          {group.items.map((item) => {
            const active = pathname === item.href;
            const Icon = item.icon;
            return (
              <Link
                key={item.href}
                href={item.href}
                onClick={onNavigate}
                title={collapsed ? item.label : undefined}
                className={cn(
                  "group relative flex items-center gap-2.5 rounded-lg px-2.5 py-1.5 text-[13px] font-medium transition-colors focus-ring",
                  active ? "bg-accent-soft text-accent" : "text-ink-dim hover:bg-bg-sunken hover:text-ink"
                )}
              >
                {active && (
                  <span className="absolute left-0 top-1/2 h-4 w-0.5 -translate-y-1/2 rounded-full bg-accent" />
                )}
                <Icon className="h-[16px] w-[16px] shrink-0" strokeWidth={1.75} />
                {!collapsed && <span className="truncate">{item.label}</span>}
              </Link>
            );
          })}
        </div>
      ))}
    </nav>
  );
}
