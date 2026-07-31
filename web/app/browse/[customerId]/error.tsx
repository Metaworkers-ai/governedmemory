"use client";

import { RouteError } from "@/components/RouteError";

export default function CustomerMemoriesError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return <RouteError error={error} reset={reset} title="Couldn't load this customer's memories" />;
}
