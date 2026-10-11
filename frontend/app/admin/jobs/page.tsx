"use client";

import * as React from "react";
import Link from "next/link";
import { Briefcase, RefreshCw, CheckCircle2, Clock, AlertTriangle, ArrowRight } from "lucide-react";
import { AppShell } from "@/components/layout/app-shell";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Spinner, ErrorState, EmptyState } from "@/components/ui/states";
import { ingestionApi } from "@/lib/api";
import { IngestionJobStatus } from "@/lib/types";

export default function AdminJobsPage() {
  const [jobs, setJobs] = React.useState<IngestionJobStatus[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);

  const stages = ["validation", "parsing", "normalization", "chunking", "embedding", "indexing", "completed"];

  const fetchJobs = React.useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await ingestionApi.listJobs();
      setJobs(data);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load ingestion jobs");
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => {
    fetchJobs();
  }, [fetchJobs]);

  return (
    <AppShell>
      <div className="p-6 max-w-6xl mx-auto space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold tracking-tight text-foreground flex items-center gap-2">
              <Briefcase className="h-5 w-5 text-primary" />
              Document Ingestion & Indexing Pipeline Monitor
            </h1>
            <p className="text-xs text-muted-foreground mt-0.5">
              Track asynchronous corpus validation, structure parsing, FastEmbed vectors, and Qdrant payloads
            </p>
          </div>

          <Button variant="outline" size="sm" onClick={fetchJobs} className="gap-1.5 text-xs">
            <RefreshCw className="h-3.5 w-3.5" /> Refresh Jobs
          </Button>
        </div>

        {/* Pipeline Stage Architecture Overview */}
        <Card className="p-4 border-border bg-card">
          <div className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-3">
            Standard Processing Stages
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-2">
            {stages.map((stg, idx) => (
              <div
                key={stg}
                className="p-2.5 rounded-md border border-border bg-muted/60 text-center space-y-1"
              >
                <span className="text-[10px] font-mono text-muted-foreground block">
                  Stage {idx + 1}
                </span>
                <span className="text-xs font-medium text-foreground capitalize block truncate">
                  {stg}
                </span>
              </div>
            ))}
          </div>
        </Card>

        {/* Jobs List */}
        <Card className="border-border bg-card">
          <CardHeader className="pb-3 border-b border-border">
            <CardTitle className="text-sm font-semibold">Active & Historical Ingestion Jobs</CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            {loading ? (
              <div className="py-12 flex justify-center">
                <Spinner className="h-6 w-6" />
              </div>
            ) : error ? (
              <div className="p-6">
                <ErrorState message={error} onRetry={fetchJobs} />
              </div>
            ) : jobs.length === 0 ? (
              <div className="p-6">
                <EmptyState
                  title="No ingestion jobs found"
                  description="When documents are ingested from the Document Library or Admin Settings, pipeline progress appears here."
                />
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="bg-muted/70 border-b border-border text-muted-foreground uppercase font-semibold">
                    <tr>
                      <th scope="col" className="px-4 py-3">Job ID</th>
                      <th scope="col" className="px-4 py-3">Document ID</th>
                      <th scope="col" className="px-4 py-3">Status</th>
                      <th scope="col" className="px-4 py-3">Current Stage</th>
                      <th scope="col" className="px-4 py-3">Progress</th>
                      <th scope="col" className="px-4 py-3 text-right">Inspect Document</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {jobs.map((j) => (
                      <tr key={j.job_id} className="hover:bg-accent/30 transition-colors">
                        <td className="px-4 py-3.5 font-mono font-medium text-foreground">
                          {j.job_id.slice(0, 8)}...
                        </td>
                        <td className="px-4 py-3.5 font-mono text-muted-foreground">
                          {j.document_id.slice(0, 8)}...
                        </td>
                        <td className="px-4 py-3.5">
                          <Badge
                            variant={
                              j.status === "completed"
                                ? "success"
                                : j.status === "failed"
                                ? "destructive"
                                : "secondary"
                            }
                            className="capitalize"
                          >
                            {j.status}
                          </Badge>
                        </td>
                        <td className="px-4 py-3.5 capitalize font-mono text-primary">
                          {j.stage || "validation"}
                        </td>
                        <td className="px-4 py-3.5">
                          <div className="w-32 bg-secondary rounded-full h-2 overflow-hidden border border-border">
                            <div
                              className="bg-primary h-2 rounded-full transition-all duration-300"
                              style={{ width: `${Math.max(5, j.progress)}%` }}
                            />
                          </div>
                          <span className="text-[10px] text-muted-foreground mt-0.5 block">
                            {j.progress}%
                          </span>
                        </td>
                        <td className="px-4 py-3.5 text-right">
                          <Link href={`/documents/${j.document_id}`}>
                            <Button variant="ghost" size="sm" className="h-6 text-xs px-2 gap-1">
                              <span>Inspect</span> <ArrowRight className="h-3 w-3" />
                            </Button>
                          </Link>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </AppShell>
  );
}
