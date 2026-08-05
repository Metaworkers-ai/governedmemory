// Next.js instrumentation hook -- register() runs once when the server
// process starts, before any request is handled. Used here to fail fast
// with a clear message if required env vars are missing, instead of letting
// the first request hit a confusing error deep in lib/backend.ts.
export async function register() {
  if (process.env.NEXT_RUNTIME !== "nodejs") return;

  const required = ["GOVERNEDMEMORY_API_URL", "GOVERNEDMEMORY_API_KEY"] as const;
  const missing = required.filter((key) => !process.env[key]);

  if (missing.length > 0) {
    console.error(
      `[startup] Missing required environment variable(s): ${missing.join(", ")}. ` +
        "Copy web/.env.example to web/.env.local and fill in your values.",
    );
    throw new Error(
      `Missing required environment variable(s): ${missing.join(", ")}. See web/.env.example.`,
    );
  }
}
