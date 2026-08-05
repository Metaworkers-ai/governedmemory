import Link from "next/link";

import { Button, Card } from "@/components/ui";

export default function NotFound() {
  return (
    <div className="mx-auto flex max-w-lg flex-col items-center gap-4 py-16 text-center animate-fade-in">
      <Card className="w-full space-y-4">
        <h1 className="gradient-accent-text text-2xl font-semibold">Page not found</h1>
        <p className="text-sm text-[var(--color-muted)]">
          The page you&rsquo;re looking for doesn&rsquo;t exist or may have moved.
        </p>
        <Link href="/write">
          <Button>Back to console</Button>
        </Link>
      </Card>
    </div>
  );
}
