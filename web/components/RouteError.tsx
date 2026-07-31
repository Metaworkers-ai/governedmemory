"use client";

import { useEffect } from "react";

import { Button, Card } from "@/components/ui";

export function RouteError({
  error,
  reset,
  title = "Something went wrong",
}: {
  error: Error & { digest?: string };
  reset: () => void;
  title?: string;
}) {
  useEffect(() => {
    console.error(JSON.stringify({
      level: "error",
      message: "route error boundary caught an error",
      time: new Date().toISOString(),
      digest: error.digest,
      error: { name: error.name, message: error.message, stack: error.stack },
    }));
  }, [error]);

  return (
    <div className="mx-auto flex max-w-lg flex-col items-center gap-4 py-16 text-center animate-fade-in">
      <Card className="w-full space-y-4">
        <span className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-red-50 text-[var(--color-danger)]">
          <svg viewBox="0 0 24 24" fill="none" className="h-6 w-6" aria-hidden="true">
            <path
              d="M12 9v4m0 4h.01M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0Z"
              stroke="currentColor"
              strokeWidth="1.7"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </span>
        <div>
          <h2 className="text-lg font-semibold text-[var(--color-text)]">{title}</h2>
          <p className="mt-1 text-sm text-[var(--color-muted)]">
            {error.message || "An unexpected error occurred while loading this page."}
          </p>
          {error.digest && (
            <p className="mt-1 text-xs text-[var(--color-muted)]">Reference: {error.digest}</p>
          )}
        </div>
        <div className="flex justify-center gap-2">
          <Button onClick={reset}>Try again</Button>
        </div>
      </Card>
    </div>
  );
}
