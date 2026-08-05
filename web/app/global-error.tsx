"use client";

import { useEffect } from "react";

// global-error.tsx replaces the ENTIRE root layout (including <html>/<body>)
// when an error escapes the root layout itself -- so it can't rely on
// globals.css/fonts/Nav rendering correctly and must be fully self-contained.
export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error(JSON.stringify({
      level: "error",
      message: "global error boundary caught an error",
      time: new Date().toISOString(),
      digest: error.digest,
      error: { name: error.name, message: error.message, stack: error.stack },
    }));
  }, [error]);

  return (
    <html lang="en">
      <body
        style={{
          margin: 0,
          minHeight: "100vh",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          fontFamily:
            "Inter, -apple-system, 'SF Pro Text', 'Segoe UI', sans-serif",
          backgroundColor: "#f8fafc",
          color: "#0f172a",
          padding: "24px",
        }}
      >
        <div
          style={{
            maxWidth: 420,
            width: "100%",
            textAlign: "center",
            border: "1px solid #e2e8f0",
            borderRadius: 16,
            padding: 32,
            backgroundColor: "#ffffff",
            boxShadow: "0 1px 2px rgba(0,0,0,0.05)",
          }}
        >
          <h1 style={{ fontSize: 20, fontWeight: 600, margin: 0 }}>
            Governed Memory hit an unexpected error
          </h1>
          <p style={{ fontSize: 14, color: "#64748b", marginTop: 8 }}>
            {error.message || "The application failed to render. Please try again."}
          </p>
          {error.digest && (
            <p style={{ fontSize: 12, color: "#64748b", marginTop: 4 }}>
              Reference: {error.digest}
            </p>
          )}
          <button
            type="button"
            onClick={reset}
            style={{
              marginTop: 20,
              backgroundImage: "linear-gradient(135deg, #2563eb, #7c3aed)",
              color: "#fff",
              border: "none",
              borderRadius: 12,
              padding: "10px 20px",
              fontSize: 14,
              fontWeight: 500,
              cursor: "pointer",
            }}
          >
            Try again
          </button>
        </div>
      </body>
    </html>
  );
}
