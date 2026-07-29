import type { Metadata } from "next";

import { AppContextProvider } from "@/components/AppContext";
import { ContextBar } from "@/components/ContextBar";
import { Nav } from "@/components/Nav";

import "./globals.css";

export const metadata: Metadata = {
  title: "Governed Memory",
  description: "Self-hosted governed memory console",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-neutral-50 text-neutral-900 antialiased">
        <AppContextProvider>
          <Nav />
          <div className="border-b border-amber-200 bg-amber-50 px-6 py-2 text-center text-xs text-amber-900">
            Hosted demo — use synthetic data only. This disposable environment may be reset by the
            operator.
          </div>
          <ContextBar />
          <main className="mx-auto max-w-5xl px-6 py-8">{children}</main>
        </AppContextProvider>
      </body>
    </html>
  );
}
