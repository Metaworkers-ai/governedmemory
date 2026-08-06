import { PageHeader } from "@/components/features/page-header";
import { Reveal } from "@/components/features/reveal";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { envVars } from "@/data/report";
import { CheckCircle2, Circle } from "lucide-react";

const categories = Array.from(new Set(envVars.map((v) => v.category)));

export default function EnvironmentVariablesPage() {
  const usedCount = envVars.filter((v) => v.used).length;
  return (
    <div>
      <PageHeader
        eyebrow="06 · Environment variables"
        title={`${envVars.length} variables across ${categories.length} categories`}
        description={`Names only — values are never displayed. ${usedCount} are actively read in code; ${envVars.length - usedCount} are declared in .env.example but not yet consumed.`}
      />

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        {categories.map((cat, i) => (
          <Reveal index={i} key={cat}>
            <Card>
              <CardHeader>
                <CardTitle>{cat}</CardTitle>
                <CardDescription>{envVars.filter((v) => v.category === cat).length} variable(s)</CardDescription>
              </CardHeader>
              <CardContent className="flex flex-col gap-1.5">
                {envVars
                  .filter((v) => v.category === cat)
                  .map((v) => (
                    <div
                      key={v.name}
                      className="flex items-center justify-between gap-3 rounded-lg border border-border-soft bg-bg-sunken px-3 py-2"
                    >
                      <div className="flex min-w-0 items-center gap-2">
                        {v.used ? (
                          <CheckCircle2 className="h-3.5 w-3.5 shrink-0 text-good" />
                        ) : (
                          <Circle className="h-3.5 w-3.5 shrink-0 text-ink-faint" />
                        )}
                        <span className="truncate font-mono text-[12.5px] text-ink">{v.name}</span>
                      </div>
                      <Badge tone={v.used ? "good" : "outline"}>{v.used ? "Used" : "Unused"}</Badge>
                    </div>
                  ))}
              </CardContent>
            </Card>
          </Reveal>
        ))}
      </div>
    </div>
  );
}
