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
          <ContextBar />
          <main className="mx-auto max-w-5xl px-6 py-8">{children}</main>
        </AppContextProvider>
      </body>
    </html>
  );
}
