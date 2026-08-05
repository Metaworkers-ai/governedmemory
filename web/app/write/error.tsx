"use client";

import { RouteError } from "@/components/RouteError";

export default function WriteError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return <RouteError error={error} reset={reset} title="Couldn't load the Write page" />;
}
