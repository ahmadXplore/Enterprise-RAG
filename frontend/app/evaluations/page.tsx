"use client";

import * as React from "react";
import Link from "next/link";
import { BarChart3, Play, Clock, CheckCircle2, ArrowRight } from "lucide-react";
import { AppShell } from "@/components/layout/app-shell";
import { MetricsOverview } from "@/components/evaluation/metrics-overview";
import { ComparisonChart } from "@/components/evaluation/comparison-chart";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Spinner, EmptyState, ErrorState } from "@/components/ui/states";
import { evaluationsApi } from "@/lib/api";
import { EvaluationRunRead } from "@/lib/types";

export default function EvaluationsPage() {
  const [runs, setRuns] = React.useState<EvaluationRunRead[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);
  const [triggering, setTriggering] = React.useState(false);

  const fetchRuns = React.useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await evaluationsApi.list({ page: 1, page_size: 10 });
      setRuns(res.items);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load evaluation runs");
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => {
    fetchRuns();
  }, [fetchRuns]);

  const handleStartRun = async () => {
    setTriggering(true);
    try {
      await evaluationsApi.create("hybrid_rerank");
      await fetchRuns();
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Could not launch evaluation run");
    } finally {
      setTriggering(false);
    }
  };

  const latestRun = runs[0];

  return (
    <AppShell>
      <div className="p-6 max-w-7xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="space-y-1">
            <h1 className="text-xl font-bold tracking-tight text-foreground flex items-center gap-2">
              <BarChart3 className="h-5 w-5 text-primary" />
              Evaluation & Benchmarking Dashboard
            </h1>
            <p className="text-xs text-muted-foreground">
              Empirical measurement of retrieval recall, MRR, groundedness, and hallucination prevention
            </p>
          </div>

          <Button
            size="sm"
            onClick={handleStartRun}
            disabled={triggering}
            className="gap-1.5 text-xs"
          >
            {triggering ? (
              <>
                <Clock className="h-3.5 w-3.5 animate-spin" /> Launching...
              </>
            ) : (
              <>
                <Play className="h-3.5 w-3.5" /> Run Evaluation Suite
              </>
            )}
          </Button>
        </div>

        {/* Top Benchmark KPI Cards */}
        <MetricsOverview metrics={latestRun?.metrics} />

        {/* Pipeline Architecture Comparison Table */}
        <ComparisonChart />

        {/* Historical Evaluation Runs */}
        <Card className="border-border bg-card">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-semibold">Evaluation Run History</CardTitle>
          </CardHeader>
          <CardContent>
            {loading ? (
              <div className="py-8 flex justify-center">
                <Spinner className="h-6 w-6" />
              </div>
            ) : error ? (
              <ErrorState message={error} onRetry={fetchRuns} />
            ) : runs.length === 0 ? (
              <div className="p-6 text-center text-xs text-muted-foreground">
                No evaluation runs have been recorded yet. Click &quot;Run Evaluation Suite&quot; to begin.
              </div>
            ) : (
              <div className="rounded-lg border border-border overflow-hidden">
                <table className="w-full text-left text-xs">
                  <thead className="bg-muted/70 border-b border-border text-muted-foreground uppercase font-semibold">
                    <tr>
                      <th scope="col" className="px-4 py-3">Run ID</th>
                      <th scope="col" className="px-4 py-3">Pipeline Type</th>
                      <th scope="col" className="px-4 py-3">Status</th>
                      <th scope="col" className="px-4 py-3">Recall@5</th>
                      <th scope="col" className="px-4 py-3">MRR</th>
                      <th scope="col" className="px-4 py-3">Groundedness</th>
                      <th scope="col" className="px-4 py-3">Started At</th>
                      <th scope="col" className="px-4 py-3 text-right">Details</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {runs.map((r) => (
                      <tr key={r.id} className="hover:bg-accent/30 transition-colors">
                        <td className="px-4 py-3 font-mono font-medium text-foreground">
                          {r.id.slice(0, 8)}...
                        </td>
                        <td className="px-4 py-3 capitalize text-muted-foreground">
                          {r.pipeline_type || "hybrid"}
                        </td>
                        <td className="px-4 py-3">
                          <Badge
                            variant={r.status === "completed" ? "success" : "secondary"}
                            className="capitalize"
                          >
                            {r.status}
                          </Badge>
                        </td>
                        <td className="px-4 py-3 font-mono">
                          {r.metrics?.recall_at_5
                            ? `${(r.metrics.recall_at_5 * 100).toFixed(1)}%`
                            : "—"}
                        </td>
                        <td className="px-4 py-3 font-mono">
                          {r.metrics?.mrr ? r.metrics.mrr.toFixed(3) : "—"}
                        </td>
                        <td className="px-4 py-3 font-mono text-emerald-700">
                          {r.metrics?.groundedness
                            ? `${(r.metrics.groundedness * 100).toFixed(1)}%`
                            : "—"}
                        </td>
                        <td className="px-4 py-3 text-muted-foreground">
                          {new Date(r.started_at).toLocaleString()}
                        </td>
                        <td className="px-4 py-3 text-right">
                          <Link href={`/evaluations/${r.id}`}>
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
