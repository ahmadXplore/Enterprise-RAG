"use client";

import * as React from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, BarChart3, CheckCircle2, Clock } from "lucide-react";
import { AppShell } from "@/components/layout/app-shell";
import { MetricsOverview } from "@/components/evaluation/metrics-overview";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Spinner, ErrorState, EmptyState } from "@/components/ui/states";
import { evaluationsApi } from "@/lib/api";
import { EvaluationRunRead } from "@/lib/types";

export default function EvaluationRunDetailPage() {
  const params = useParams();
  const id = Array.isArray(params.id) ? params.id[0] : params.id;

  const [run, setRun] = React.useState<EvaluationRunRead | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);

  const fetchRun = React.useCallback(async () => {
    if (!id) return;
    setLoading(true);
    setError(null);
    try {
      const data = await evaluationsApi.get(id);
      setRun(data);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load evaluation run details");
    } finally {
      setLoading(false);
    }
  }, [id]);

  React.useEffect(() => {
    fetchRun();
  }, [fetchRun]);

  return (
    <AppShell>
      <div className="p-6 max-w-5xl mx-auto space-y-6">
        <Link
          href="/evaluations"
          className="text-xs text-muted-foreground hover:text-foreground inline-flex items-center gap-1.5 transition-colors"
        >
          <ArrowLeft className="h-3.5 w-3.5" /> Back to Evaluations
        </Link>

        {loading ? (
          <div className="py-20 flex justify-center">
            <Spinner className="h-8 w-8" />
          </div>
        ) : error ? (
          <ErrorState message={error} onRetry={fetchRun} />
        ) : !run ? (
          <EmptyState title="Evaluation run not found" />
        ) : (
          <div className="space-y-6">
            <Card className="p-6 border-border">
              <div className="flex items-center justify-between">
                <div>
                  <div className="flex items-center gap-2">
                    <BarChart3 className="h-5 w-5 text-primary" />
                    <h1 className="text-lg font-bold tracking-tight text-foreground">
                      Evaluation Run: {run.id}
                    </h1>
                    <Badge variant={run.status === "completed" ? "success" : "secondary"}>
                      {run.status}
                    </Badge>
                  </div>
                  <p className="text-xs text-muted-foreground mt-1">
                    Pipeline: <span className="font-mono text-foreground">{run.pipeline_type}</span> • Started:{" "}
                    {new Date(run.started_at).toLocaleString()}
                  </p>
                </div>
              </div>
            </Card>

            <MetricsOverview metrics={run.metrics} />

            <Card className="border-border bg-card">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-semibold">Evaluation Configuration</CardTitle>
              </CardHeader>
              <CardContent>
                <pre className="p-4 rounded-lg bg-muted border border-border text-xs font-mono text-foreground overflow-x-auto">
                  {JSON.stringify(run.configuration || { mode: "hybrid", top_k: 20 }, null, 2)}
                </pre>
              </CardContent>
            </Card>
          </div>
        )}
      </div>
    </AppShell>
  );
}
