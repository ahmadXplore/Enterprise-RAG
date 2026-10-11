"use client";

import * as React from "react";
import Link from "next/link";
import {
  FileText,
  CheckCircle2,
  Database,
  MessageSquare,
  Activity,
  ArrowRight,
  Search,
} from "lucide-react";
import { AppShell } from "@/components/layout/app-shell";
import { Badge } from "@/components/ui/badge";
import { Spinner, EmptyState } from "@/components/ui/states";
import { documentsApi, healthApi } from "@/lib/api";
import { DocumentRead, HealthStatus, CorpusStats } from "@/lib/types";

export default function DashboardPage() {
  const [loading, setLoading] = React.useState(true);
  const [docs, setDocs] = React.useState<DocumentRead[]>([]);
  const [totalDocs, setTotalDocs] = React.useState(0);
  const [stats, setStats] = React.useState<CorpusStats | null>(null);
  const [health, setHealth] = React.useState<Record<string, HealthStatus>>({});

  React.useEffect(() => {
    let isMounted = true;

    async function loadData() {
      try {
        const [docsRes, qdrantHealth, redisHealth, llmHealth, statsRes] = await Promise.allSettled([
          documentsApi.list({ page: 1, page_size: 5 }),
          healthApi.qdrant(),
          healthApi.redis(),
          healthApi.llm(),
          healthApi.stats(),
        ]);

        if (!isMounted) return;

        if (docsRes.status === "fulfilled") {
          setDocs(docsRes.value.items);
          setTotalDocs(docsRes.value.total);
        }

        if (statsRes.status === "fulfilled") {
          setStats(statsRes.value);
        }

        const h: Record<string, HealthStatus> = {};
        if (qdrantHealth.status === "fulfilled") h["qdrant"] = qdrantHealth.value;
        if (redisHealth.status === "fulfilled") h["redis"] = redisHealth.value;
        if (llmHealth.status === "fulfilled") h["llm"] = llmHealth.value;
        setHealth(h);
      } finally {
        if (isMounted) setLoading(false);
      }
    }

    loadData();
    return () => {
      isMounted = false;
    };
  }, []);

  const totalDocumentsCount = stats?.total_documents ?? totalDocs;
  const readyDocsCount = stats?.ready_documents ?? null;
  const indexedChunksCount = stats?.total_chunks ?? null;
  const metrics = [
    { label: "Documents", value: totalDocumentsCount, icon: FileText },
    { label: "Ready to search", value: readyDocsCount, icon: CheckCircle2 },
    { label: "Indexed passages", value: indexedChunksCount, icon: Database },
    { label: "Queries", value: stats?.total_queries ?? null, icon: MessageSquare },
  ];

  return (
    <AppShell>
      <div className="mx-auto min-h-full max-w-7xl px-5 py-8 sm:px-8 lg:px-10">
        <section className="flex flex-col gap-6 border-b border-border pb-8 sm:flex-row sm:items-end sm:justify-between">
          <div className="max-w-xl space-y-3">
            <p className="text-[11px] font-semibold uppercase text-primary">Document intelligence / Overview</p>
            <h1 className="font-serif text-3xl font-semibold text-foreground sm:text-4xl">Workspace overview</h1>
            <p className="text-sm text-muted-foreground">A live view of your indexed corpus and retrieval services.</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Link
              href="/search"
              className="inline-flex h-10 items-center gap-2 rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
            >
              <Search className="h-4 w-4" /> Search corpus
            </Link>
            <Link
              href="/documents"
              className="inline-flex h-10 items-center gap-2 rounded-md border border-border bg-card px-4 text-sm font-medium text-foreground transition-colors hover:bg-accent"
            >
              <FileText className="h-4 w-4" /> Documents
            </Link>
          </div>
        </section>

        <section aria-label="Corpus metrics" className="grid grid-cols-2 border-b border-border md:grid-cols-4">
          {metrics.map(({ label, value, icon: Icon }, index) => (
            <div key={label} className={`min-w-0 py-5 pr-3 sm:py-7 sm:pr-6 ${index > 0 ? "border-l border-border pl-3 sm:pl-6" : ""}`}>
              <div className="mb-3 flex items-center gap-2 text-xs text-muted-foreground">
                <Icon className="h-4 w-4 text-primary" aria-hidden="true" />
                <span>{label}</span>
              </div>
              <p className="font-serif text-3xl text-foreground sm:text-4xl">
                {loading || value === null ? "—" : value.toLocaleString()}
              </p>
            </div>
          ))}
        </section>

        <div className="grid grid-cols-1 gap-10 py-8 lg:grid-cols-[minmax(0,1.6fr)_minmax(16rem,0.8fr)] lg:gap-14">
          <section>
            <div className="mb-4 flex items-center justify-between">
              <div>
                <h2 className="font-serif text-xl text-foreground">Recently added</h2>
                <p className="mt-1 text-xs text-muted-foreground">The latest files in your corpus</p>
              </div>
              <Link href="/documents" className="inline-flex items-center gap-1 text-xs font-medium text-primary hover:underline">
                All documents <ArrowRight className="h-3.5 w-3.5" />
              </Link>
            </div>

            {loading ? (
              <div className="flex justify-center py-12">
                <Spinner className="h-6 w-6" />
              </div>
            ) : docs.length === 0 ? (
              <EmptyState
                title="No documents yet"
                description="Upload or register documents in the Document Library or Admin Settings."
              />
            ) : (
              <div className="divide-y divide-border border-y border-border">
                {docs.map((doc) => (
                  <div key={doc.id} className="flex items-center justify-between gap-4 py-4 transition-colors hover:bg-white/60">
                    <div className="min-w-0 space-y-1.5">
                      <Link
                        href={`/documents/${doc.id}`}
                        className="block truncate text-sm font-medium text-foreground transition-colors hover:text-primary"
                      >
                        {doc.title}
                      </Link>
                      <div className="flex flex-wrap gap-x-3 text-xs text-muted-foreground">
                        {doc.organization && <span>{doc.organization}</span>}
                        {doc.report_year && <span>{doc.report_year}</span>}
                        <span className="capitalize">{doc.document_type.replaceAll("_", " ")}</span>
                      </div>
                    </div>
                    <Badge variant={doc.status === "ready" ? "success" : "secondary"}>
                      {doc.status}
                    </Badge>
                  </div>
                ))}
              </div>
            )}
          </section>

          <aside className="space-y-9">
            <section>
              <div className="mb-4 flex items-center gap-2">
                <Activity className="h-4 w-4 text-primary" />
                <h2 className="font-serif text-xl text-foreground">System health</h2>
              </div>
              <div className="divide-y divide-border border-y border-border">
                {[
                  { key: "qdrant", label: "Vector database" },
                  { key: "redis", label: "Cache service" },
                  { key: "llm", label: "Language model" },
                ].map(({ key, label }) => {
                  const online = health[key]?.status === "ok";
                  return (
                    <div key={key} className="flex items-center justify-between gap-3 py-3 text-sm">
                      <span className="text-foreground">{label}</span>
                      <span className="flex items-center gap-2 text-xs text-muted-foreground">
                        <span className={`h-2 w-2 rounded-full ${online ? "bg-emerald-600" : "bg-amber-500"}`} />
                        {online ? "Online" : loading ? "Checking" : "Unavailable"}
                      </span>
                    </div>
                  );
                })}
              </div>
            </section>

            <section>
              <h2 className="mb-3 font-serif text-xl text-foreground">Go to</h2>
              <div className="space-y-1">
                {[
                  { href: "/search", label: "Search documents", icon: Search },
                  { href: "/chat", label: "Ask a question", icon: MessageSquare },
                  { href: "/documents", label: "Browse library", icon: FileText },
                ].map(({ href, label, icon: Icon }) => (
                  <Link key={href} href={href} className="group flex items-center gap-3 rounded-md px-2 py-2.5 text-sm text-muted-foreground transition-colors hover:bg-white/70 hover:text-foreground">
                    <Icon className="h-4 w-4 text-primary" />
                    <span className="flex-1">{label}</span>
                    <ArrowRight className="h-3.5 w-3.5 opacity-0 transition-opacity group-hover:opacity-100" />
                  </Link>
                ))}
              </div>
            </section>
          </aside>
        </div>
      </div>
    </AppShell>
  );
}
