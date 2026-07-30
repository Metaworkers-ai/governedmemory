"use client";

import { useAppContext } from "./AppContext";

export function ContextBar() {
  const { customerId, agentId, sessionId, setCustomerId, setAgentId, setSessionId } = useAppContext();

  const fieldClasses =
    "rounded-lg border border-[var(--color-border)] bg-white px-2.5 py-1.5 text-sm text-[var(--color-text)] transition-colors focus:border-[var(--color-primary)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]/20";

  return (
    <div className="border-b border-[var(--color-border)] bg-slate-50">
      <div className="flex w-full flex-wrap items-center gap-4 px-4 py-2.5 text-sm sm:px-6 lg:px-8">
        <span className="text-xs font-semibold uppercase tracking-wide text-[var(--color-muted)]">
          Context
        </span>
        <label className="flex items-center gap-1.5">
          <span className="text-[var(--color-muted)]">Customer</span>
          <input
            className={fieldClasses}
            value={customerId}
            onChange={(e) => setCustomerId(e.target.value)}
          />
        </label>
        <label className="flex items-center gap-1.5">
          <span className="text-[var(--color-muted)]">Agent</span>
          <input className={fieldClasses} value={agentId} onChange={(e) => setAgentId(e.target.value)} />
        </label>
        <label className="flex items-center gap-1.5">
          <span className="text-[var(--color-muted)]">Session</span>
          <input
            className={fieldClasses}
            value={sessionId}
            onChange={(e) => setSessionId(e.target.value)}
          />
        </label>
      </div>
    </div>
  );
}
