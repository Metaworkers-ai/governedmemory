"use client";

import { RouteError } from "@/components/RouteError";

export default function SignUpError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return <RouteError error={error} reset={reset} title="Couldn't load Sign Up" />;
}
