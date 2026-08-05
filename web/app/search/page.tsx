"use client";

import { useState, useTransition } from "react";

import { retrieveAction } from "@/app/actions";
import { useAppContext } from "@/components/AppContext";
import {
  Button,
  Card,
  EmptyState,
  ErrorBanner,
  Field,
  Input,
  PageHeader,
  Select,
  Skeleton,
  TaintBadge,
} from "@/components/ui";
import type { MemoryRecord } from "@/lib/types";

const KNOWN_PURPOSES = ["(no filter — any purpose)", "cx_support", "billing", "sales", "security", "retention"];

function highlight(text: string, query: string) {
  if (!query.trim()) return text;
  const parts = text.split(new RegExp(`(${query.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")})`, "gi"));
  return parts.map((part, i) =>
    part.toLowerCase() === query.toLowerCase() ? (
      <mark key={i} className="rounded bg-amber-200/70 px-0.5 text-inherit">
        {part}
      </mark>
    ) : (
      <span key={i}>{part}</span>
    ),
  );
}

function ResultSkeletons() {
  return (
    <div className="space-y-3">
      {[0, 1, 2].map((i) => (
        <Card key={i} className="flex items-start gap-3">
          <Skeleton className="h-5 w-16" />
          <div className="min-w-0 flex-1 space-y-2">
            <Skeleton className="h-4 w-3/4" />
            <Skeleton className="h-3 w-1/2" />
          </div>
        </Card>
      ))}
    </div>
  );
}

export default function SearchPage() {
  const { agentId, sessionId } = useAppContext();
  const [query, setQuery] = useState("");
  const [purpose, setPurpose] = useState(KNOWN_PURPOSES[0]);
  const [k, setK] = useState(5);
  const [includeUntrusted, setIncludeUntrusted] = useState(false);

  const [isPending, startTransition] = useTransition();
  const [results, setResults] = useState<MemoryRecord[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  function submit() {
    setError(null);
    startTransition(async () => {
      const outcome = await retrieveAction({
        query,
        agent_id: agentId,
        session_id: sessionId,
        purpose: purpose === KNOWN_PURPOSES[0] ? null : purpose,
        k,
        include_untrusted: includeUntrusted,
      });
      if (outcome.ok) {
        setResults(outcome.data);
      } else {
        setError(outcome.error);
        setResults(null);
      }
    });
  }

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <PageHeader
        title="Search"
        description={
          <>
            Governed hybrid search — fused vector + lexical results, then the privilege gate (taint +
            purpose) and policy engine. This shows the same governed results an agent calling{" "}
            <code className="rounded bg-slate-100 px-1 py-0.5 font-mono text-xs">/v1/retrieve</code> would
            get; the raw ungated vector/lexical comparison from the Streamlit demo isn&apos;t exposed by
            the REST API, so it isn&apos;t reproduced here.
          </>
        }
      />

      <Card className="space-y-4">
        <Field label="Query">
          <div className="relative">
            <svg
              viewBox="0 0 24 24"
              fill="none"
              className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--color-muted)]"
              aria-hidden="true"
            >
              <circle cx="11" cy="11" r="7" stroke="currentColor" strokeWidth="1.7" />
              <path d="m20 20-3-3" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" />
            </svg>
            <Input
              className="pl-10"
              placeholder="refund policy"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && submit()}
            />
          </div>
        </Field>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <Field label="Purpose">
            <Select value={purpose} onChange={(e) => setPurpose(e.target.value)}>
              {KNOWN_PURPOSES.map((p) => (
                <option key={p} value={p}>
                  {p}
                </option>
              ))}
            </Select>
          </Field>
          <Field label={`Max results (k=${k})`}>
            <input
              type="range"
              min={1}
              max={20}
              value={k}
              onChange={(e) => setK(Number(e.target.value))}
              className="w-full accent-[var(--color-primary)]"
            />
          </Field>
          <Field label="Options">
            <label className="flex items-center gap-2 pt-2 text-sm text-[var(--color-text)]">
              <input
                type="checkbox"
                checked={includeUntrusted}
                onChange={(e) => setIncludeUntrusted(e.target.checked)}
                className="h-4 w-4 rounded accent-[var(--color-primary)]"
              />
              Include untrusted/quarantined
            </label>
          </Field>
        </div>
        <Button loading={isPending} disabled={isPending || !query} onClick={submit}>
          {isPending ? "Searching…" : "Search"}
        </Button>
        {error && <ErrorBanner>{error}</ErrorBanner>}
      </Card>

      {isPending && <ResultSkeletons />}

      {!isPending && results && (
        <div className="space-y-3">
          {results.length === 0 ? (
            <EmptyState>
              No results — try a broader query, a different purpose, or check &ldquo;include
              untrusted&rdquo;.
            </EmptyState>
          ) : (
            results.map((r) => (
              <Card key={r.id} hoverable className="flex items-start gap-3">
                <TaintBadge taint={r.trust.taint} />
                <div className="min-w-0 flex-1">
                  <p className="text-sm leading-relaxed text-[var(--color-text)]">
                    {highlight(r.content, query)}
                  </p>
                  <p className="mt-1.5 text-xs text-[var(--color-muted)]">
                    purposes={r.purpose.allowed_purposes.length ? r.purpose.allowed_purposes.join(", ") : "any"}{" "}
                    · source={r.provenance.source_type}
                  </p>
                </div>
              </Card>
            ))
          )}
        </div>
      )}
    </div>
  );
}
