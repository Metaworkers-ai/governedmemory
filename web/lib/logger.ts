// Minimal structured logger. No external log shipper is wired up (this repo
// is self-hosted with no logging backend to talk to) -- this exists so every
// caught error goes through one place with a consistent shape, ready to be
// piped to a real sink later without touching call sites.

type Level = "debug" | "info" | "warn" | "error";

interface LogFields {
  [key: string]: unknown;
}

function emit(level: Level, message: string, fields?: LogFields) {
  const entry = {
    level,
    message,
    time: new Date().toISOString(),
    ...fields,
  };
  const method = level === "debug" ? "log" : level;
  console[method](JSON.stringify(entry));
}

export const logger = {
  debug: (message: string, fields?: LogFields) => emit("debug", message, fields),
  info: (message: string, fields?: LogFields) => emit("info", message, fields),
  warn: (message: string, fields?: LogFields) => emit("warn", message, fields),
  error: (message: string, error?: unknown, fields?: LogFields) =>
    emit("error", message, {
      ...fields,
      error:
        error instanceof Error
          ? { name: error.name, message: error.message, stack: error.stack }
          : error,
    }),
};
