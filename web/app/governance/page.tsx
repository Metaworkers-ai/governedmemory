"use client";

import { useEffect, useState, useTransition } from "react";

import { deleteMemoryAction, listMemoriesAction, quarantineMemoryAction } from "@/app/actions";
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
  SuccessBanner,
  TaintBadge,
} from "@/components/ui";
import type { MemoryRecord } from "@/lib/types";

export default function GovernancePage() {
  const { customerId } = useAppContext();
  const [memories, setMemories] = useState<MemoryRecord[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState("");
  const [reason, setReason] = useState("potential prompt injection");
  const [isPending, startTransition] = useTransition();
  const [message, setMessage] = useState<{ kind: "success" | "error"; text: string } | null>(null);

  function reload() {
    startTransition(async () => {
      const outcome = await listMemoriesAction(customerId);
      if (outcome.ok) {
        setMemories(outcome.data);
        setLoadError(null);
        if (!outcome.data.find((m) => m.id === selectedId)) {
          setSelectedId(outcome.data[0]?.id ?? "");
        }
      } else {
        setLoadError(outcome.error);
      }
    });
  }

  // eslint-disable-next-line react-hooks/exhaustive-deps -- refetch only when the customer changes
  useEffect(reload, [customerId]);

  function runQuarantine() {
    startTransition(async () => {
      const outcome = await quarantineMemoryAction(selectedId, reason);
      setMessage(
        outcome.ok
          ? { kind: "success", text: "Quarantined." }
          : { kind: "error", text: outcome.error },
      );
      if (outcome.ok) reload();
    });
  }

  function runDelete() {
    startTransition(async () => {
      const outcome = await deleteMemoryAction(selectedId);
      setMessage(
        outcome.ok
          ? { kind: "success", text: "Deleted permanently." }
          : { kind: "error", text: outcome.error },
      );
      if (outcome.ok) reload();
    });
  }

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <PageHeader
        title="Quarantine / Delete"
        description={
          <>
            Acting on memories for customer{" "}
            <code className="rounded bg-slate-100 px-1 py-0.5 font-mono text-xs">{customerId}</code>{" "}
            (change the Customer field above to switch).
          </>
        }
      />

      {loadError && <ErrorBanner>{loadError}</ErrorBanner>}

      {memories === null && !loadError ? (
        <Card className="space-y-3">
          <Skeleton className="h-9 w-full" />
          <Skeleton className="h-9 w-1/3" />
        </Card>
      ) : memories && memories.length === 0 ? (
        <EmptyState>No memories for this customer yet.</EmptyState>
      ) : (
        <Card className="space-y-4">
          <Field label="Select a memory">
            <Select value={selectedId} onChange={(e) => setSelectedId(e.target.value)}>
              {(memories ?? []).map((m) => (
                <option key={m.id} value={m.id}>
                  {m.content.slice(0, 60)} ({m.trust.taint})
                </option>
              ))}
            </Select>
          </Field>
          {selectedId && (
            <div className="flex items-center gap-2 text-xs text-[var(--color-muted)]">
              <TaintBadge taint={memories?.find((m) => m.id === selectedId)?.trust.taint ?? "trusted"} />
              <code className="font-mono">{selectedId}</code>
            </div>
          )}

          <div className="grid grid-cols-1 gap-4 border-t border-[var(--color-border)] pt-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Field label="Quarantine reason">
                <Input value={reason} onChange={(e) => setReason(e.target.value)} />
              </Field>
              <Button
                variant="secondary"
                loading={isPending}
                disabled={isPending || !selectedId}
                onClick={runQuarantine}
              >
                Quarantine
              </Button>
            </div>
            <div className="space-y-2">
              <p className="text-sm font-medium text-[var(--color-text)]">Permanent removal</p>
              <Button variant="danger" loading={isPending} disabled={isPending || !selectedId} onClick={runDelete}>
                Delete permanently
              </Button>
            </div>
          </div>

          {message && (message.kind === "success" ? (
            <SuccessBanner>{message.text}</SuccessBanner>
          ) : (
            <ErrorBanner>{message.text}</ErrorBanner>
          ))}
        </Card>
      )}
    </div>
  );
}
