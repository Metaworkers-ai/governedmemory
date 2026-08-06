import { PageHeader } from "@/components/features/page-header";
import { Reveal } from "@/components/features/reveal";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { frontendInfo } from "@/data/report";
import { FileCode } from "lucide-react";

export default function FrontendPage() {
  return (
    <div>
      <PageHeader
        eyebrow="04 · Frontend analysis"
        title={`${frontendInfo.framework} ${frontendInfo.version}`}
        description={frontendInfo.routing}
      />

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Reveal index={0}>
          <Card className="h-full">
            <CardHeader>
              <CardTitle>Pages</CardTitle>
              <CardDescription>App Router pages found in web/app.</CardDescription>
            </CardHeader>
            <CardContent className="flex flex-col gap-2">
              {frontendInfo.pages.map((p) => (
                <div key={p.path} className="flex items-start justify-between gap-3 rounded-lg border border-border-soft bg-bg-sunken px-3 py-2.5">
                  <span className="font-mono text-[12.5px] text-accent">{p.path}</span>
                  <span className="text-right text-[12.5px] text-ink-dim">{p.purpose}</span>
                </div>
              ))}
            </CardContent>
          </Card>
        </Reveal>

        <Reveal index={1}>
          <Card className="h-full">
            <CardHeader>
              <CardTitle>Configuration files</CardTitle>
              <CardDescription>Detected in web/.</CardDescription>
            </CardHeader>
            <CardContent className="flex flex-wrap gap-2">
              {frontendInfo.configFiles.map((f) => (
                <Badge key={f} tone="neutral">
                  <FileCode className="h-3 w-3" />
                  {f}
                </Badge>
              ))}
            </CardContent>
            <CardHeader className="pt-2">
              <CardTitle>Components observed</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-wrap gap-2">
              {frontendInfo.components.map((c) => (
                <Badge key={c} tone="outline">
                  {c}
                </Badge>
              ))}
            </CardContent>
          </Card>
        </Reveal>
      </div>

      <Reveal index={2} className="mt-4">
        <Card>
          <CardHeader>
            <CardTitle>Notes</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-[13px] leading-relaxed text-ink-dim">{frontendInfo.note}</p>
          </CardContent>
        </Card>
      </Reveal>
    </div>
  );
}
