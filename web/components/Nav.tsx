"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const LINKS = [
  { href: "/write", label: "Write" },
  { href: "/browse", label: "Browse" },
  { href: "/search", label: "Search" },
  { href: "/governance", label: "Governance" },
  { href: "/audit", label: "Audit Log" },
];

export function Nav() {
  const pathname = usePathname();

  return (
    <header className="border-b border-neutral-200 bg-white">
      <div className="mx-auto flex max-w-5xl items-center gap-6 px-6 py-4">
        <span className="text-sm font-semibold tracking-tight text-neutral-900">
          Governed Memory
        </span>
        <nav className="flex gap-1">
          {LINKS.map((link) => {
            const active = pathname === link.href || pathname.startsWith(link.href + "/");
            return (
              <Link
                key={link.href}
                href={link.href}
                className={`rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
                  active
                    ? "bg-neutral-900 text-white"
                    : "text-neutral-600 hover:bg-neutral-100 hover:text-neutral-900"
                }`}
              >
                {link.label}
              </Link>
            );
          })}
        </nav>
      </div>
    </header>
  );
}
