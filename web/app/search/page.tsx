"use client";

import { useState, useTransition } from "react";

import { retrieveAction } from "@/app/actions";
import { useAppContext } from "@/components/AppContext";
import { Button, Card, EmptyState, ErrorBanner, Field, Input, Select, TaintBadge } from "@/components/ui";
import type { MemoryRecord } from "@/lib/types";

const KNOWN_PURPOSES = ["(no filter — any purpose)", "cx_support", "billing", "sales", "security", "retention"];

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
    <div className="space-y-6">
      <div>
        <h1 className="text-lg font-semibold text-neutral-900">Search</h1>
        <p className="mt-1 text-sm text-neutral-600">
          Governed hybrid search — fused vector + lexical results, then the privilege gate (taint +
          purpose) and policy engine. This shows the same governed results an agent calling{" "}
          <code className="font-mono text-xs">/v1/retrieve</code> would get; the raw ungated
          vector/lexical comparison from the Streamlit demo isn&apos;t exposed by the REST API, so it
          isn&apos;t reproduced here.
        </p>
      </div>

      <Card className="space-y-4">
        <Field label="Query">
          <Input
            placeholder="refund policy"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && submit()}
          />
        </Field>
        <div className="grid grid-cols-3 gap-4">
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
              className="w-full"
            />
          </Field>
          <Field label="Options">
            <label className="flex items-center gap-2 pt-2 text-sm text-neutral-700">
              <input
                type="checkbox"
                checked={includeUntrusted}
                onChange={(e) => setIncludeUntrusted(e.target.checked)}
              />
              Include untrusted/quarantined
            </label>
          </Field>
        </div>
        <Button onClick={submit} disabled={isPending || !query}>
          {isPending ? "Searching…" : "Search"}
        </Button>
        {error && <ErrorBanner>{error}</ErrorBanner>}
      </Card>

      {results && (
        <div className="space-y-2">
          {results.length === 0 ? (
            <EmptyState>
              No results — try a broader query, a different purpose, or check &ldquo;include
              untrusted&rdquo;.
            </EmptyState>
          ) : (
            results.map((r) => (
              <Card key={r.id} className="flex items-start gap-3">
                <TaintBadge taint={r.trust.taint} />
                <div className="min-w-0 flex-1">
                  <p className="text-sm text-neutral-800">{r.content}</p>
                  <p className="mt-1 text-xs text-neutral-500">
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
