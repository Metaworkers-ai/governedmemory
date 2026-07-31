"use client";

import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

interface WorkingContext {
  customerId: string;
  agentId: string;
  sessionId: string;
  setCustomerId: (v: string) => void;
  setAgentId: (v: string) => void;
  setSessionId: (v: string) => void;
}

const Ctx = createContext<WorkingContext | null>(null);

const STORAGE_KEY = "governedmemory.workingContext";

export function AppContextProvider({ children }: { children: ReactNode }) {
  const [customerId, setCustomerId] = useState("cust-1");
  const [agentId, setAgentId] = useState("cx-agent-1");
  const [sessionId, setSessionId] = useState("web-session-1");

  // Hydrate from localStorage after mount -- keeps server/client render identical
  // on first paint, since localStorage isn't available during SSR. A lazy useState
  // initializer can't replace this: it would run during SSR too and throw on
  // `window`. This is the documented exception to react-hooks/set-state-in-effect
  // (syncing React state from an external, client-only source on mount).
  useEffect(() => {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return;
    try {
      const saved = JSON.parse(raw);
      // eslint-disable-next-line react-hooks/set-state-in-effect
      if (saved.customerId) setCustomerId(saved.customerId);
      if (saved.agentId) setAgentId(saved.agentId);
      if (saved.sessionId) setSessionId(saved.sessionId);
    } catch {
      // ignore malformed storage
    }
  }, []);

  useEffect(() => {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify({ customerId, agentId, sessionId }));
  }, [customerId, agentId, sessionId]);

  // Memoized so consumers only re-render when these values actually change,
  // not on every render of a parent that happens to re-render this provider.
  const value = useMemo(
    () => ({ customerId, agentId, sessionId, setCustomerId, setAgentId, setSessionId }),
    [customerId, agentId, sessionId],
  );

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useAppContext(): WorkingContext {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useAppContext must be used within AppContextProvider");
  return ctx;
}
