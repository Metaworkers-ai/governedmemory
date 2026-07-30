import type { Metadata } from "next";
import { Inter } from "next/font/google";

import { AppContextProvider } from "@/components/AppContext";
import { ContextBar } from "@/components/ContextBar";
import { Nav } from "@/components/Nav";

import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Governed Memory",
  description: "Self-hosted governed memory console",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className={inter.variable}>
      <body className="min-h-screen bg-[var(--color-bg)] font-sans text-[var(--color-text)] antialiased">
        <AppContextProvider>
          <Nav />
          <ContextBar />
          <main className="w-full px-4 py-8 sm:px-6 lg:px-8 animate-fade-in">{children}</main>
        </AppContextProvider>
      </body>
    </html>
  );
}
