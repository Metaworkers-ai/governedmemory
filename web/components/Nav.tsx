"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";

const LINKS = [
  { href: "/write", label: "Home" },
  { href: "/browse", label: "Browse" },
  { href: "/search", label: "Search" },
  { href: "/governance", label: "Governance" },
  { href: "/audit", label: "Audit Log" },
];

function LogoMark() {
  return (
    <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-[var(--color-primary)] text-sm font-bold text-white shadow-sm">
      G
    </span>
  );
}

export function Nav() {
  const pathname = usePathname();
  const [mobileOpen, setMobileOpen] = useState(false);

  const isActive = (href: string) => pathname === href || pathname.startsWith(href + "/");

  return (
    <header className="sticky top-0 z-40 w-full border-b border-[var(--color-border)] bg-white/80 backdrop-blur-md">
      <div className="flex w-full items-center justify-between px-4 py-3 sm:px-6 lg:px-8">
        <div className="flex items-center gap-3">
          <Link href="/write" className="flex items-center gap-2" onClick={() => setMobileOpen(false)}>
            <LogoMark />
            <span className="text-sm font-semibold tracking-tight text-[var(--color-text)]">
              Governed Memory
            </span>
          </Link>
        </div>

        <nav className="hidden items-center gap-1 md:flex">
          {LINKS.map((link) => {
            const active = isActive(link.href);
            return (
              <Link
                key={link.href}
                href={link.href}
                className={`relative rounded-lg px-3.5 py-2 text-sm font-medium transition-colors duration-150 ${
                  active
                    ? "text-[var(--color-primary)]"
                    : "text-[var(--color-muted)] hover:bg-slate-100 hover:text-[var(--color-text)]"
                }`}
              >
                {link.label}
                {active && (
                  <span className="absolute inset-x-3 -bottom-[13px] h-0.5 rounded-full bg-[var(--color-primary)]" />
                )}
              </Link>
            );
          })}
        </nav>

        <div className="hidden items-center gap-2 md:flex">
          <Link
            href="/signup"
            className="inline-flex items-center justify-center rounded-xl bg-[var(--color-primary)] px-4 py-2 text-sm font-medium text-white shadow-sm transition-all duration-150 hover:bg-[var(--color-primary-hover)] active:scale-[0.98]"
          >
            Sign Up
          </Link>
        </div>

        <button
          type="button"
          aria-label={mobileOpen ? "Close menu" : "Open menu"}
          aria-expanded={mobileOpen}
          onClick={() => setMobileOpen((v) => !v)}
          className="flex h-9 w-9 items-center justify-center rounded-lg text-[var(--color-text)] transition-colors hover:bg-slate-100 md:hidden"
        >
          <svg viewBox="0 0 24 24" fill="none" className="h-5 w-5" aria-hidden="true">
            {mobileOpen ? (
              <path
                d="M6 6l12 12M18 6L6 18"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
              />
            ) : (
              <path
                d="M4 7h16M4 12h16M4 17h16"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
              />
            )}
          </svg>
        </button>
      </div>

      {mobileOpen && (
        <nav className="animate-slide-up border-t border-[var(--color-border)] bg-white px-4 py-3 md:hidden">
          <div className="flex flex-col gap-1">
            {LINKS.map((link) => {
              const active = isActive(link.href);
              return (
                <Link
                  key={link.href}
                  href={link.href}
                  onClick={() => setMobileOpen(false)}
                  className={`rounded-lg px-3.5 py-2.5 text-sm font-medium transition-colors ${
                    active
                      ? "bg-blue-50 text-[var(--color-primary)]"
                      : "text-[var(--color-muted)] hover:bg-slate-100 hover:text-[var(--color-text)]"
                  }`}
                >
                  {link.label}
                </Link>
              );
            })}
            <Link
              href="/signup"
              onClick={() => setMobileOpen(false)}
              className="mt-2 inline-flex items-center justify-center rounded-xl bg-[var(--color-primary)] px-4 py-2.5 text-sm font-medium text-white shadow-sm"
            >
              Sign Up
            </Link>
          </div>
        </nav>
      )}
    </header>
  );
}
