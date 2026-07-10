"use client";

import { useAppContext } from "./AppContext";

export function ContextBar() {
  const { customerId, agentId, sessionId, setCustomerId, setAgentId, setSessionId } = useAppContext();

  const fieldClasses =
    "rounded-md border border-neutral-300 bg-white px-2 py-1 text-sm text-neutral-900 focus:border-neutral-500 focus:outline-none focus:ring-1 focus:ring-neutral-500";

  return (
    <div className="border-b border-neutral-200 bg-neutral-100">
      <div className="mx-auto flex max-w-5xl flex-wrap items-center gap-4 px-6 py-2 text-sm">
        <span className="text-xs font-medium uppercase tracking-wide text-neutral-500">Context</span>
        <label className="flex items-center gap-1.5">
          <span className="text-neutral-600">Customer</span>
          <input
            className={fieldClasses}
            value={customerId}
            onChange={(e) => setCustomerId(e.target.value)}
          />
        </label>
        <label className="flex items-center gap-1.5">
          <span className="text-neutral-600">Agent</span>
          <input className={fieldClasses} value={agentId} onChange={(e) => setAgentId(e.target.value)} />
        </label>
        <label className="flex items-center gap-1.5">
          <span className="text-neutral-600">Session</span>
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
