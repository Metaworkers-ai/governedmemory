import { PageHeader } from "@/components/features/page-header";
import { Reveal } from "@/components/features/reveal";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { StatusBadge } from "@/components/ui/badge";
import { CategoryDonut } from "@/components/features/charts";
import { packages } from "@/data/report";

const categories = Array.from(new Set(packages.map((p) => p.category)));

export default function PackagesPage() {
  const chartData = categories.map((c) => ({ name: c, value: packages.filter((p) => p.category === c).length }));

  return (
    <div>
      <PageHeader
        eyebrow="05 · Packages & dependencies"
        title={`${packages.length} tracked packages`}
        description="Categorized from pyproject.toml, requirements.txt, and web/package.json. Status reflects whether the package is actually exercised in code."
      />

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[280px_1fr]">
        <Reveal index={0}>
          <Card className="h-full">
            <CardHeader>
              <CardTitle>By category</CardTitle>
            </CardHeader>
            <CardContent>
              <CategoryDonut data={chartData} />
              <div className="mt-2 flex flex-col gap-1.5">
                {chartData.map((d) => (
                  <div key={d.name} className="flex items-center justify-between text-[12.5px]">
                    <span className="text-ink-dim">{d.name}</span>
                    <span className="font-mono text-ink">{d.value}</span>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </Reveal>

        <div className="flex flex-col gap-4">
          {categories.map((cat, ci) => (
            <Reveal index={ci + 1} key={cat}>
              <Card>
                <CardHeader>
                  <CardTitle>{cat}</CardTitle>
                  <CardDescription>{packages.filter((p) => p.category === cat).length} package(s)</CardDescription>
                </CardHeader>
                <CardContent className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                  {packages
                    .filter((p) => p.category === cat)
                    .map((p) => (
                      <div key={p.name} className="flex items-start justify-between gap-3 rounded-lg border border-border-soft bg-bg-sunken px-3 py-2.5">
                        <div className="min-w-0">
                          <p className="truncate font-mono text-[12.5px] font-medium text-ink">{p.name}</p>
                          <p className="mt-0.5 text-[11px] text-ink-faint">{p.version}</p>
                          <p className="mt-1 text-[12px] text-ink-dim">{p.purpose}</p>
                        </div>
                        <StatusBadge status={p.status} />
                      </div>
                    ))}
                </CardContent>
              </Card>
            </Reveal>
          ))}
        </div>
      </div>
    </div>
  );
}
