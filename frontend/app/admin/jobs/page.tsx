"use client";

import * as React from "react";
import Link from "next/link";
import {
  Upload,
  RefreshCw,
  CheckCircle2,
  Clock,
  AlertTriangle,
  ArrowRight,
  FileText,
  AlertCircle,
  XCircle,
  Activity,
  Timer,
  ChevronRight,
  ChevronDown,
  ChevronUp,
  BarChart3,
  Layers,
  Search,
  Copy,
  Check,
  ExternalLink,
  Play,
  Pause,
  LayoutGrid,
  Table as TableIcon,
  ShieldCheck,
  Zap,
  Info,
  Terminal,
  X,
  Database,
  Cpu
} from "lucide-react";
import { AppShell } from "@/components/layout/app-shell";
import { Button } from "@/components/ui/button";
import { ingestionApi } from "@/lib/api";
import { IngestionJobStatus } from "@/lib/types";

// Stage definition & metadata
const STAGES = [
  { key: "validation", label: "Validation", desc: "MIME type, size & schema check", icon: ShieldCheck },
  { key: "parsing", label: "Parsing", desc: "Text & structural extraction", icon: FileText },
  { key: "chunking", label: "Chunking", desc: "Semantic & token splitting", icon: Layers },
  { key: "embedding", label: "Embedding", desc: "Vector embeddings calculation", icon: Cpu },
  { key: "indexing", label: "Indexing", desc: "Vector database upsert", icon: Database },
];

const STAGE_KEYS = STAGES.map((s) => s.key);

function formatDuration(startedAt?: string | null, completedAt?: string | null): string {
  if (!startedAt) return "—";
  const start = new Date(startedAt).getTime();
  const end = completedAt ? new Date(completedAt).getTime() : Date.now();
  const diffSec = Math.max(0, Math.round((end - start) / 1000));
  if (diffSec < 60) return `${diffSec}s`;
  const mins = Math.floor(diffSec / 60);
  const secs = diffSec % 60;
  return `${mins}m ${secs}s`;
}

function timeAgo(dateStr?: string | null): string {
  if (!dateStr) return "—";
  const diff = Date.now() - new Date(dateStr).getTime();
  const sec = Math.floor(diff / 1000);
  if (sec < 60) return "just now";
  const min = Math.floor(sec / 60);
  if (min < 60) return `${min}m ago`;
  const hr = Math.floor(min / 60);
  if (hr < 24) return `${hr}h ago`;
  const days = Math.floor(hr / 24);
  return `${days}d ago`;
}

function CopyPill({ text, label }: { text: string; label?: string }) {
  const [copied, setCopied] = React.useState(false);

  const onCopy = (e: React.MouseEvent) => {
    e.stopPropagation();
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <button
      onClick={onCopy}
      type="button"
      title="Click to copy full ID"
      className="inline-flex items-center gap-1 font-mono text-[11px] px-2 py-0.5 rounded-md bg-muted/60 hover:bg-muted text-muted-foreground hover:text-foreground transition-colors border border-border/50"
    >
      <span>{label || text.slice(0, 8) + "..."}</span>
      {copied ? <Check className="h-3 w-3 text-emerald-500" /> : <Copy className="h-3 w-3 opacity-60" />}
    </button>
  );
}

function StatusBadge({ status }: { status: string }) {
  if (status === "completed") {
    return (
      <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20">
        <CheckCircle2 className="h-3 w-3 shrink-0" />
        Completed
      </span>
    );
  }
  if (status === "failed") {
    return (
      <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-red-500/10 text-red-600 dark:text-red-400 border border-red-500/20">
        <XCircle className="h-3 w-3 shrink-0" />
        Failed
      </span>
    );
  }
  if (status === "queued") {
    return (
      <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/20">
        <Clock className="h-3 w-3 shrink-0" />
        Queued
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-primary/10 text-primary border border-primary/25">
      <span className="relative flex h-2 w-2">
        <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-primary opacity-75" />
        <span className="relative inline-flex rounded-full h-2 w-2 bg-primary" />
      </span>
      Running
    </span>
  );
}

function MiniStepTracker({ currentStage, status }: { currentStage: string; status: string }) {
  const currentIdx = STAGE_KEYS.indexOf(currentStage);
  const isCompleted = status === "completed";
  const isFailed = status === "failed";

  return (
    <div className="flex items-center gap-1" title={`Stage: ${currentStage}`}>
      {STAGES.map((s, idx) => {
        const isDone = isCompleted || idx < currentIdx;
        const isActive = !isCompleted && !isFailed && s.key === currentStage;

        return (
          <React.Fragment key={s.key}>
            <div
              className={`h-2 w-2 rounded-full transition-all ${
                isFailed && s.key === currentStage
                  ? "bg-red-500 ring-2 ring-red-500/30"
                  : isDone
                  ? "bg-emerald-500"
                  : isActive
                  ? "bg-primary ring-2 ring-primary/40 animate-pulse scale-125"
                  : "bg-muted-foreground/25"
              }`}
            />
            {idx < STAGES.length - 1 && (
              <div
                className={`h-0.5 w-2 transition-all ${
                  isDone ? "bg-emerald-500/70" : "bg-muted-foreground/20"
                }`}
              />
            )}
          </React.Fragment>
        );
      })}
    </div>
  );
}

function FullPipelineStepper({ currentStage, status }: { currentStage: string; status: string }) {
  const currentIdx = STAGE_KEYS.indexOf(currentStage);
  const isCompleted = status === "completed";
  const isFailed = status === "failed";

  return (
    <div className="grid grid-cols-5 gap-2 w-full pt-1">
      {STAGES.map((s, idx) => {
        const Icon = s.icon;
        const isDone = isCompleted || idx < currentIdx;
        const isActive = !isCompleted && !isFailed && s.key === currentStage;

        return (
          <div
            key={s.key}
            className={`relative p-2.5 rounded-xl border text-left transition-all ${
              isActive
                ? "bg-primary/10 border-primary/40 shadow-sm shadow-primary/10 ring-1 ring-primary/20"
                : isDone
                ? "bg-emerald-500/5 border-emerald-500/25 text-foreground"
                : isFailed && s.key === currentStage
                ? "bg-red-500/10 border-red-500/30"
                : "bg-muted/30 border-border/40 opacity-60"
            }`}
          >
            <div className="flex items-center justify-between mb-1.5">
              <div
                className={`h-6 w-6 rounded-lg flex items-center justify-center ${
                  isActive
                    ? "bg-primary text-primary-foreground animate-pulse"
                    : isDone
                    ? "bg-emerald-500/20 text-emerald-600 dark:text-emerald-400"
                    : isFailed && s.key === currentStage
                    ? "bg-red-500/20 text-red-500"
                    : "bg-muted text-muted-foreground"
                }`}
              >
                {isDone ? (
                  <Check className="h-3.5 w-3.5" />
                ) : (
                  <Icon className="h-3.5 w-3.5" />
                )}
              </div>
              <span className="text-[10px] font-mono text-muted-foreground">0{idx + 1}</span>
            </div>
            <p className="text-xs font-semibold leading-tight text-foreground truncate">{s.label}</p>
            <p className="text-[10px] text-muted-foreground truncate mt-0.5 hidden sm:block">{s.desc}</p>
          </div>
        );
      })}
    </div>
  );
}
export default function AdminJobsPage() {
  const [jobs, setJobs] = React.useState<IngestionJobStatus[]>([]);
  const [skeleton, setSkeleton] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);
  const [isRefreshing, setIsRefreshing] = React.useState(false);
  const [lastRefreshed, setLastRefreshed] = React.useState<Date | null>(null);

  // User controls
  const [search, setSearch] = React.useState("");
  const [filterStatus, setFilterStatus] = React.useState<string>("all");
  const [viewMode, setViewMode] = React.useState<"table" | "cards">("table");
  const [autoRefresh, setAutoRefresh] = React.useState(true);
  const [inspectedJob, setInspectedJob] = React.useState<IngestionJobStatus | null>(null);

  const fetchJobs = React.useCallback(async (isFirstLoad = false) => {
    if (!isFirstLoad) setIsRefreshing(true);
    setError(null);
    try {
      const data = await ingestionApi.listJobs();
      setJobs(data);
      setLastRefreshed(new Date());
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load ingestion jobs");
    } finally {
      setSkeleton(false);
      setIsRefreshing(false);
    }
  }, []);

  React.useEffect(() => {
    fetchJobs(true);
  }, [fetchJobs]);

  // Dynamic Polling: 3s if active jobs exist, 15s if idle, paused if autoRefresh is off
  React.useEffect(() => {
    if (!autoRefresh) return;
    const hasActive = jobs.some(
      (j) => j.status === "queued" || j.status === "processing" || j.status === "running"
    );
    const intervalMs = hasActive ? 3000 : 15000;
    const timer = setInterval(() => {
      fetchJobs(false);
    }, intervalMs);
    return () => clearInterval(timer);
  }, [fetchJobs, jobs, autoRefresh]);

  // Metrics
  const totalCount = jobs.length;
  const activeCount = jobs.filter((j) => j.status === "processing" || j.status === "running").length;
  const queuedCount = jobs.filter((j) => j.status === "queued").length;
  const completedCount = jobs.filter((j) => j.status === "completed").length;
  const failedCount = jobs.filter((j) => j.status === "failed").length;
  const successRate = totalCount > 0 ? Math.round((completedCount / totalCount) * 100) : 100;

  // Most prominent active job
  const spotlightJob = jobs.find((j) => j.status === "processing" || j.status === "running") || null;

  // Filter & Search
  const filteredJobs = React.useMemo(() => {
    return jobs.filter((job) => {
      if (filterStatus === "active") {
        if (job.status !== "processing" && job.status !== "running") return false;
      } else if (filterStatus === "queued") {
        if (job.status !== "queued") return false;
      } else if (filterStatus === "completed") {
        if (job.status !== "completed") return false;
      } else if (filterStatus === "failed") {
        if (job.status !== "failed") return false;
      }

      if (search.trim()) {
        const q = search.toLowerCase();
        const titleMatch = (job.document_title || "").toLowerCase().includes(q);
        const idMatch = job.job_id.toLowerCase().includes(q);
        const docIdMatch = job.document_id.toLowerCase().includes(q);
        if (!titleMatch && !idMatch && !docIdMatch) return false;
      }

      return true;
    });
  }, [jobs, filterStatus, search]);

  return (
    <AppShell>
      <div className="min-h-screen bg-background pb-16">
        {/* Top Hero / Command Bar */}
        <div className="border-b border-border bg-gradient-to-b from-card/80 to-background/50 backdrop-blur-md sticky top-0 z-20">
          <div className="px-6 py-5 max-w-7xl mx-auto">
            <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
              <div>
                <div className="flex items-center gap-3">
                  <div className="h-10 w-10 rounded-xl bg-primary/10 border border-primary/20 flex items-center justify-center text-primary shadow-sm">
                    <Activity className="h-5 w-5" />
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <h1 className="text-xl font-bold tracking-tight text-foreground">Ingestion Queue & Pipeline</h1>
                      <span className="text-[10px] font-mono uppercase px-2 py-0.5 rounded-md bg-secondary text-secondary-foreground font-semibold border border-border">
                        Enterprise RAG
                      </span>
                    </div>
                    <p className="text-xs text-muted-foreground mt-0.5 flex items-center gap-2">
                      <span>Document vectorization, semantic chunking & indexing engine</span>
                      {lastRefreshed && (
                        <>
                          <span className="text-muted-foreground/40">•</span>
                          <span className="text-muted-foreground/70">
                            Synced {lastRefreshed.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })}
                          </span>
                        </>
                      )}
                    </p>
                  </div>
                </div>
              </div>

              {/* Action Toolbar */}
              <div className="flex items-center flex-wrap gap-2.5">
                {/* Auto Refresh Toggle */}
                <button
                  type="button"
                  onClick={() => setAutoRefresh(!autoRefresh)}
                  className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-medium border transition-colors ${
                    autoRefresh
                      ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/30"
                      : "bg-muted text-muted-foreground border-border hover:text-foreground"
                  }`}
                  title={autoRefresh ? "Auto-refresh is active (3s / 15s)" : "Auto-refresh paused"}
                >
                  {autoRefresh ? (
                    <>
                      <span className="relative flex h-2 w-2">
                        <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-500 opacity-75" />
                        <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500" />
                      </span>
                      <span>Live Feed</span>
                    </>
                  ) : (
                    <>
                      <Pause className="h-3 w-3" />
                      <span>Paused</span>
                    </>
                  )}
                </button>

                {/* Manual Refresh */}
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => fetchJobs(false)}
                  disabled={isRefreshing}
                  className="h-8 text-xs rounded-xl gap-1.5"
                >
                  <RefreshCw className={`h-3.5 w-3.5 ${isRefreshing ? "animate-spin text-primary" : ""}`} />
                  <span>Refresh</span>
                </Button>

                {/* Trigger Upload */}
                <Link href="/documents">
                  <Button size="sm" className="h-8 text-xs rounded-xl gap-1.5 shadow-sm shadow-primary/20">
                    <Upload className="h-3.5 w-3.5" />
                    <span>Upload Document</span>
                  </Button>
                </Link>
              </div>
            </div>
          </div>
        </div>

        <div className="px-6 py-6 max-w-7xl mx-auto space-y-6">
          {/* Error Banner */}
          {error && (
            <div className="flex items-center justify-between p-4 bg-red-500/10 border border-red-500/25 rounded-2xl text-red-600 dark:text-red-400 text-xs">
              <div className="flex items-center gap-3">
                <AlertCircle className="h-4 w-4 shrink-0" />
                <p className="font-medium">{error}</p>
              </div>
              <Button variant="ghost" size="sm" onClick={() => fetchJobs(true)} className="h-7 text-xs">
                Retry
              </Button>
            </div>
          )}

          {/* KPI Metrics Strip */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3.5">
            {/* Total */}
            <div className="p-4 rounded-2xl border border-border bg-card/60 backdrop-blur-sm relative overflow-hidden group hover:border-primary/40 transition-all">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Total Ingestions</span>
                <div className="h-8 w-8 rounded-lg bg-muted/60 flex items-center justify-center text-muted-foreground">
                  <FileText className="h-4 w-4" />
                </div>
              </div>
              <p className="text-2xl font-bold text-foreground mt-2 tabular-nums">{totalCount}</p>
              <p className="text-[11px] text-muted-foreground mt-1">Lifetime document jobs</p>
            </div>

            {/* Active / Running */}
            <div
              onClick={() => setFilterStatus(activeCount > 0 ? "active" : "all")}
              className={`p-4 rounded-2xl border bg-card/60 backdrop-blur-sm relative overflow-hidden cursor-pointer transition-all ${
                activeCount > 0
                  ? "border-primary/40 shadow-sm shadow-primary/10 ring-1 ring-primary/20"
                  : "border-border hover:border-border/80"
              }`}
            >
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">In Progress</span>
                <div
                  className={`h-8 w-8 rounded-lg flex items-center justify-center ${
                    activeCount > 0 ? "bg-primary/20 text-primary animate-pulse" : "bg-muted/60 text-muted-foreground"
                  }`}
                >
                  <Activity className="h-4 w-4" />
                </div>
              </div>
              <div className="flex items-baseline gap-2 mt-2">
                <p className={`text-2xl font-bold tabular-nums ${activeCount > 0 ? "text-primary" : "text-foreground"}`}>
                  {activeCount}
                </p>
                {queuedCount > 0 && (
                  <span className="text-xs font-medium text-amber-500">(+{queuedCount} queued)</span>
                )}
              </div>
              <p className="text-[11px] text-muted-foreground mt-1">Active pipeline workers</p>
            </div>

            {/* Success Rate */}
            <div className="p-4 rounded-2xl border border-border bg-card/60 backdrop-blur-sm relative overflow-hidden group hover:border-emerald-500/40 transition-all">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Success Rate</span>
                <div className="h-8 w-8 rounded-lg bg-emerald-500/10 flex items-center justify-center text-emerald-500">
                  <CheckCircle2 className="h-4 w-4" />
                </div>
              </div>
              <div className="flex items-baseline gap-2 mt-2">
                <p className="text-2xl font-bold text-emerald-600 dark:text-emerald-400 tabular-nums">{successRate}%</p>
                <span className="text-xs text-muted-foreground">({completedCount} done)</span>
              </div>
              <div className="w-full bg-secondary h-1.5 rounded-full overflow-hidden mt-2">
                <div className="bg-emerald-500 h-full rounded-full transition-all duration-500" style={{ width: `${successRate}%` }} />
              </div>
            </div>

            {/* Failures */}
            <div
              onClick={() => setFilterStatus(failedCount > 0 ? "failed" : "all")}
              className={`p-4 rounded-2xl border bg-card/60 backdrop-blur-sm relative overflow-hidden cursor-pointer transition-all ${
                failedCount > 0 ? "border-red-500/30 hover:border-red-500/50" : "border-border hover:border-border/80"
              }`}
            >
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Failed Jobs</span>
                <div
                  className={`h-8 w-8 rounded-lg flex items-center justify-center ${
                    failedCount > 0 ? "bg-red-500/10 text-red-500" : "bg-muted/60 text-muted-foreground"
                  }`}
                >
                  <AlertTriangle className="h-4 w-4" />
                </div>
              </div>
              <p className={`text-2xl font-bold tabular-nums mt-2 ${failedCount > 0 ? "text-red-500" : "text-foreground"}`}>
                {failedCount}
              </p>
              <p className="text-[11px] text-muted-foreground mt-1">
                {failedCount > 0 ? "Click to filter errors" : "Zero pipeline faults"}
              </p>
            </div>
          </div>

          {/* Live Pipeline Spotlight (Rendered if any job is active) */}
          {spotlightJob && (
            <div className="rounded-2xl border border-primary/30 bg-gradient-to-r from-primary/10 via-card to-primary/5 p-5 shadow-lg shadow-primary/5 relative overflow-hidden">
              <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-4">
                <div className="flex items-center gap-3">
                  <div className="h-10 w-10 rounded-xl bg-primary/20 text-primary flex items-center justify-center">
                    <Zap className="h-5 w-5 animate-pulse" />
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-[11px] font-bold uppercase tracking-wider text-primary">Live Pipeline Spotlight</span>
                      <span className="h-1.5 w-1.5 rounded-full bg-primary animate-ping" />
                    </div>
                    <h3 className="text-base font-bold text-foreground mt-0.5">
                      {spotlightJob.document_title || "Untitled Document"}
                    </h3>
                  </div>
                </div>

                <div className="flex items-center gap-3">
                  <CopyPill text={spotlightJob.job_id} label={"Job #" + spotlightJob.job_id.slice(0, 8)} />
                  <div className="text-right">
                    <div className="text-xs font-bold text-foreground tabular-nums">{spotlightJob.progress}% complete</div>
                    <div className="text-[11px] text-muted-foreground flex items-center gap-1 justify-end">
                      <Timer className="h-3 w-3" />
                      {formatDuration(spotlightJob.started_at, null)}
                    </div>
                  </div>
                </div>
              </div>

              {/* Progress bar */}
              <div className="relative h-2 w-full bg-secondary/80 rounded-full overflow-hidden mb-4">
                <div
                  className="h-full bg-primary rounded-full transition-all duration-500 shadow-sm shadow-primary"
                  style={{ width: `${Math.max(5, spotlightJob.progress)}%` }}
                />
              </div>

              {/* 5-step interactive track */}
              <FullPipelineStepper currentStage={spotlightJob.stage} status={spotlightJob.status} />
            </div>
          )}

          {/* Filter & View Toolbar */}
          <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 pt-2">
            {/* Search Input */}
            <div className="relative flex-1 max-w-md">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <input
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Filter by document title or job UUID..."
                className="w-full h-9 pl-9 pr-8 text-xs bg-card border border-border rounded-xl focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary text-foreground placeholder:text-muted-foreground"
              />
              {search && (
                <button
                  type="button"
                  onClick={() => setSearch("")}
                  className="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                >
                  <X className="h-3.5 w-3.5" />
                </button>
              )}
            </div>

            <div className="flex items-center gap-2 self-end sm:self-auto">
              {/* Status Filter Tabs */}
              <div className="flex items-center p-1 bg-muted/60 border border-border rounded-xl text-xs">
                {[
                  { key: "all", label: `All (${totalCount})` },
                  { key: "active", label: `Active (${activeCount})` },
                  { key: "completed", label: `Done (${completedCount})` },
                  { key: "failed", label: `Failed (${failedCount})` },
                ].map((tab) => (
                  <button
                    key={tab.key}
                    type="button"
                    onClick={() => setFilterStatus(tab.key)}
                    className={`px-2.5 py-1 rounded-lg font-medium transition-all ${
                      filterStatus === tab.key
                        ? "bg-card text-foreground shadow-xs font-semibold"
                        : "text-muted-foreground hover:text-foreground"
                    }`}
                  >
                    {tab.label}
                  </button>
                ))}
              </div>

              {/* View Mode Toggle */}
              <div className="flex items-center p-1 bg-muted/60 border border-border rounded-xl text-xs">
                <button
                  type="button"
                  onClick={() => setViewMode("table")}
                  className={`p-1.5 rounded-lg transition-colors ${
                    viewMode === "table" ? "bg-card text-foreground shadow-xs" : "text-muted-foreground hover:text-foreground"
                  }`}
                  title="Table Console View"
                >
                  <TableIcon className="h-4 w-4" />
                </button>
                <button
                  type="button"
                  onClick={() => setViewMode("cards")}
                  className={`p-1.5 rounded-lg transition-colors ${
                    viewMode === "cards" ? "bg-card text-foreground shadow-xs" : "text-muted-foreground hover:text-foreground"
                  }`}
                  title="Visual Cards View"
                >
                  <LayoutGrid className="h-4 w-4" />
                </button>
              </div>
            </div>
          </div>
          {/* Main Content Area */}
          {skeleton ? (
            <div className="space-y-3">
              {Array.from({ length: 4 }).map((_, i) => (
                <div key={i} className="h-20 rounded-2xl border border-border bg-card/40 animate-pulse" />
              ))}
            </div>
          ) : filteredJobs.length === 0 ? (
            <div className="rounded-2xl border border-dashed border-border p-12 text-center bg-card/30 flex flex-col items-center justify-center">
              <div className="h-12 w-12 rounded-2xl bg-muted/80 flex items-center justify-center text-muted-foreground mb-3">
                <FileText className="h-6 w-6" />
              </div>
              <h3 className="text-sm font-semibold text-foreground">No Ingestion Jobs Found</h3>
              <p className="text-xs text-muted-foreground mt-1 max-w-sm">
                {search || filterStatus !== "all"
                  ? "No jobs matched your current filter criteria. Try clearing search or selecting All."
                  : "No documents have been ingested yet. Upload a PDF or DOCX file to initiate the pipeline."}
              </p>
              {search || filterStatus !== "all" ? (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    setSearch("");
                    setFilterStatus("all");
                  }}
                  className="mt-4 text-xs rounded-xl"
                >
                  Reset Filters
                </Button>
              ) : (
                <Link href="/documents" className="mt-4">
                  <Button size="sm" className="text-xs rounded-xl gap-1.5">
                    <Upload className="h-3.5 w-3.5" /> Upload First Document
                  </Button>
                </Link>
              )}
            </div>
          ) : viewMode === "table" ? (
            /* =================== TABLE VIEW =================== */
            <div className="rounded-2xl border border-border bg-card overflow-hidden shadow-xs">
              <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse text-xs">
                  <thead>
                    <tr className="border-b border-border bg-muted/30 text-muted-foreground font-semibold uppercase text-[10px] tracking-wider">
                      <th className="py-3.5 px-4 font-medium">Document & Job ID</th>
                      <th className="py-3.5 px-4 font-medium">Status</th>
                      <th className="py-3.5 px-4 font-medium">Pipeline Stage</th>
                      <th className="py-3.5 px-4 font-medium">Progress</th>
                      <th className="py-3.5 px-4 font-medium">Duration & Time</th>
                      <th className="py-3.5 px-4 font-medium text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border/60">
                    {filteredJobs.map((job) => {
                      const isActive = job.status === "processing" || job.status === "running";
                      const isInspected = inspectedJob?.job_id === job.job_id;

                      return (
                        <tr
                          key={job.job_id}
                          onClick={() => setInspectedJob(isInspected ? null : job)}
                          className={`group cursor-pointer transition-colors ${
                            isInspected
                              ? "bg-primary/5"
                              : isActive
                              ? "bg-primary/[0.02] hover:bg-primary/[0.05]"
                              : "hover:bg-muted/40"
                          }`}
                        >
                          {/* Document Title & Job ID */}
                          <td className="py-3.5 px-4">
                            <div className="flex items-center gap-3">
                              <div
                                className={`h-8 w-8 rounded-lg flex items-center justify-center shrink-0 ${
                                  job.status === "completed"
                                    ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400"
                                    : job.status === "failed"
                                    ? "bg-red-500/10 text-red-500"
                                    : "bg-primary/10 text-primary"
                                }`}
                              >
                                <FileText className="h-4 w-4" />
                              </div>
                              <div className="min-w-0 max-w-xs sm:max-w-sm">
                                <p className="font-semibold text-foreground truncate group-hover:text-primary transition-colors">
                                  {job.document_title || "Untitled Document"}
                                </p>
                                <div className="flex items-center gap-2 mt-0.5">
                                  <CopyPill text={job.job_id} />
                                </div>
                              </div>
                            </div>
                          </td>

                          {/* Status */}
                          <td className="py-3.5 px-4 whitespace-nowrap">
                            <StatusBadge status={job.status} />
                          </td>

                          {/* Stage Tracker */}
                          <td className="py-3.5 px-4">
                            <div className="flex items-center gap-2">
                              <MiniStepTracker currentStage={job.stage} status={job.status} />
                              <span className="text-xs font-medium text-foreground capitalize">{job.stage}</span>
                            </div>
                          </td>

                          {/* Progress bar */}
                          <td className="py-3.5 px-4 min-w-[130px]">
                            <div className="space-y-1">
                              <div className="flex items-center justify-between text-[11px] font-mono text-muted-foreground">
                                <span>{job.progress}%</span>
                              </div>
                              <div className="h-1.5 w-full bg-secondary rounded-full overflow-hidden">
                                <div
                                  className={`h-full rounded-full transition-all duration-500 ${
                                    job.status === "failed"
                                      ? "bg-red-500"
                                      : job.status === "completed"
                                      ? "bg-emerald-500"
                                      : "bg-primary"
                                  }`}
                                  style={{ width: `${Math.max(4, job.progress)}%` }}
                                />
                              </div>
                            </div>
                          </td>

                          {/* Timing & Duration */}
                          <td className="py-3.5 px-4 whitespace-nowrap">
                            <div className="text-xs font-medium text-foreground">
                              {formatDuration(job.started_at, job.completed_at)}
                            </div>
                            <div className="text-[10px] text-muted-foreground flex items-center gap-1 mt-0.5">
                              <Clock className="h-3 w-3" />
                              {timeAgo(job.completed_at || job.started_at)}
                            </div>
                          </td>

                          {/* Actions */}
                          <td className="py-3.5 px-4 text-right whitespace-nowrap">
                            <div className="flex items-center justify-end gap-1.5">
                              {job.status === "completed" && (
                                <Link
                                  href={`/documents/${job.document_id}`}
                                  onClick={(e) => e.stopPropagation()}
                                  title="Open Document Detail"
                                >
                                  <Button variant="ghost" size="sm" className="h-7 w-7 p-0 rounded-lg text-primary hover:bg-primary/10">
                                    <ExternalLink className="h-3.5 w-3.5" />
                                  </Button>
                                </Link>
                              )}
                              <Button
                                variant="ghost"
                                size="sm"
                                className="h-7 px-2 text-xs rounded-lg gap-1 text-muted-foreground hover:text-foreground"
                              >
                                <span>Inspect</span>
                                {isInspected ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
                              </Button>
                            </div>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          ) : (
            /* =================== CARDS VIEW =================== */
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {filteredJobs.map((job) => {
                const isActive = job.status === "processing" || job.status === "running";
                const isInspected = inspectedJob?.job_id === job.job_id;

                return (
                  <div
                    key={job.job_id}
                    onClick={() => setInspectedJob(isInspected ? null : job)}
                    className={`group rounded-2xl border bg-card p-5 cursor-pointer transition-all duration-200 relative overflow-hidden flex flex-col justify-between ${
                      isActive
                        ? "border-primary/40 shadow-md shadow-primary/5 ring-1 ring-primary/20"
                        : job.status === "failed"
                        ? "border-red-500/30 hover:border-red-500/50"
                        : "border-border hover:border-border/80 hover:shadow-sm"
                    }`}
                  >
                    {/* Top status bar accent */}
                    <div
                      className={`absolute top-0 left-0 right-0 h-1 ${
                        isActive
                          ? "bg-primary animate-pulse"
                          : job.status === "completed"
                          ? "bg-emerald-500"
                          : job.status === "failed"
                          ? "bg-red-500"
                          : "bg-amber-500"
                      }`}
                    />

                    <div>
                      {/* Header */}
                      <div className="flex items-start justify-between gap-3 mb-3">
                        <div className="flex items-center gap-3 min-w-0">
                          <div
                            className={`h-10 w-10 rounded-xl flex items-center justify-center shrink-0 ${
                              job.status === "completed"
                                ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400"
                                : job.status === "failed"
                                ? "bg-red-500/10 text-red-500"
                                : "bg-primary/10 text-primary"
                            }`}
                          >
                            <FileText className="h-5 w-5" />
                          </div>
                          <div className="min-w-0">
                            <h4 className="font-semibold text-sm text-foreground truncate group-hover:text-primary transition-colors">
                              {job.document_title || "Untitled Document"}
                            </h4>
                            <div className="flex items-center gap-2 mt-0.5">
                              <CopyPill text={job.job_id} />
                              <span className="text-muted-foreground/30 text-xs">•</span>
                              <span className="text-[11px] text-muted-foreground font-mono">
                                {formatDuration(job.started_at, job.completed_at)}
                              </span>
                            </div>
                          </div>
                        </div>

                        <StatusBadge status={job.status} />
                      </div>

                      {/* Progress & Stepper */}
                      <div className="space-y-2 mt-4">
                        <div className="flex items-center justify-between text-xs">
                          <span className="text-muted-foreground font-medium flex items-center gap-1.5">
                            <span>Stage:</span>
                            <span className="text-foreground font-semibold capitalize">{job.stage}</span>
                          </span>
                          <span className="font-mono font-bold text-foreground">{job.progress}%</span>
                        </div>

                        <div className="h-1.5 w-full bg-secondary rounded-full overflow-hidden">
                          <div
                            className={`h-full rounded-full transition-all duration-500 ${
                              job.status === "failed"
                                ? "bg-red-500"
                                : job.status === "completed"
                                ? "bg-emerald-500"
                                : "bg-primary"
                            }`}
                            style={{ width: `${Math.max(4, job.progress)}%` }}
                          />
                        </div>

                        {/* Mini Pipeline dots */}
                        <div className="pt-2">
                          <FullPipelineStepper currentStage={job.stage} status={job.status} />
                        </div>
                      </div>

                      {/* Error Preview */}
                      {job.status === "failed" && job.error_message && (
                        <div className="mt-3 p-2.5 rounded-xl bg-red-500/10 border border-red-500/20 text-red-600 dark:text-red-400 text-xs flex items-start gap-2">
                          <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
                          <p className="line-clamp-2 text-[11px] font-mono leading-relaxed">{job.error_message}</p>
                        </div>
                      )}
                    </div>

                    {/* Footer */}
                    <div className="mt-4 pt-3 border-t border-border/50 flex items-center justify-between text-xs text-muted-foreground">
                      <span className="flex items-center gap-1 text-[11px]">
                        <Clock className="h-3 w-3" />
                        {timeAgo(job.completed_at || job.started_at)}
                      </span>

                      <div className="flex items-center gap-2">
                        {job.status === "completed" && (
                          <Link
                            href={`/documents/${job.document_id}`}
                            onClick={(e) => e.stopPropagation()}
                            className="inline-flex items-center gap-1 text-xs text-primary hover:underline font-medium"
                          >
                            <span>View Doc</span>
                            <ExternalLink className="h-3 w-3" />
                          </Link>
                        )}
                        <span className="text-xs font-medium text-muted-foreground group-hover:text-foreground flex items-center gap-0.5">
                          <span>Details</span>
                          <ChevronRight className="h-3 w-3" />
                        </span>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          {/* Interactive Inspection Drawer / Modal */}
          {inspectedJob && (
            <div className="rounded-2xl border border-primary/30 bg-card p-6 shadow-xl relative overflow-hidden animate-in fade-in zoom-in-95 duration-200">
              <div className="flex items-start justify-between gap-4 pb-4 border-b border-border">
                <div className="flex items-center gap-3">
                  <div
                    className={`h-10 w-10 rounded-xl flex items-center justify-center ${
                      inspectedJob.status === "completed"
                        ? "bg-emerald-500/10 text-emerald-500"
                        : inspectedJob.status === "failed"
                        ? "bg-red-500/10 text-red-500"
                        : "bg-primary/10 text-primary"
                    }`}
                  >
                    <Terminal className="h-5 w-5" />
                  </div>
                  <div>
                    <h3 className="text-base font-bold text-foreground">
                      {inspectedJob.document_title || "Untitled Document"}
                    </h3>
                    <div className="flex items-center gap-3 text-xs text-muted-foreground mt-0.5 flex-wrap">
                      <span>Job ID: <CopyPill text={inspectedJob.job_id} label={inspectedJob.job_id} /></span>
                      <span>Doc ID: <CopyPill text={inspectedJob.document_id} label={inspectedJob.document_id} /></span>
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  {inspectedJob.status === "completed" && (
                    <Link href={`/documents/${inspectedJob.document_id}`}>
                      <Button size="sm" variant="outline" className="h-8 text-xs gap-1.5 rounded-xl">
                        <ExternalLink className="h-3.5 w-3.5" /> View Document
                      </Button>
                    </Link>
                  )}
                  <button
                    type="button"
                    onClick={() => setInspectedJob(null)}
                    className="h-8 w-8 rounded-xl bg-muted/80 hover:bg-muted text-muted-foreground hover:text-foreground flex items-center justify-center"
                  >
                    <X className="h-4 w-4" />
                  </button>
                </div>
              </div>

              {/* Inspector Content */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-6 pt-5">
                {/* Meta details */}
                <div className="space-y-4 text-xs">
                  <div className="p-3.5 rounded-xl bg-muted/30 border border-border/50 space-y-2">
                    <p className="font-semibold text-muted-foreground text-[11px] uppercase tracking-wider">Execution Timings</p>
                    <div className="flex justify-between py-1 border-b border-border/40">
                      <span className="text-muted-foreground">Status</span>
                      <StatusBadge status={inspectedJob.status} />
                    </div>
                    <div className="flex justify-between py-1 border-b border-border/40">
                      <span className="text-muted-foreground">Current Stage</span>
                      <span className="font-semibold capitalize text-foreground">{inspectedJob.stage}</span>
                    </div>
                    <div className="flex justify-between py-1 border-b border-border/40">
                      <span className="text-muted-foreground">Total Duration</span>
                      <span className="font-mono font-medium text-foreground">
                        {formatDuration(inspectedJob.started_at, inspectedJob.completed_at)}
                      </span>
                    </div>
                    <div className="flex justify-between py-1 border-b border-border/40">
                      <span className="text-muted-foreground">Started At</span>
                      <span className="font-mono text-muted-foreground">
                        {inspectedJob.started_at ? new Date(inspectedJob.started_at).toLocaleTimeString() : "—"}
                      </span>
                    </div>
                    <div className="flex justify-between py-1">
                      <span className="text-muted-foreground">Completed At</span>
                      <span className="font-mono text-muted-foreground">
                        {inspectedJob.completed_at ? new Date(inspectedJob.completed_at).toLocaleTimeString() : "—"}
                      </span>
                    </div>
                  </div>
                </div>

                {/* Pipeline Stages Breakdown */}
                <div className="md:col-span-2 space-y-3">
                  <p className="font-semibold text-muted-foreground text-[11px] uppercase tracking-wider">
                    Pipeline Lifecycle Stages
                  </p>
                  <div className="space-y-2">
                    {STAGES.map((s, idx) => {
                      const Icon = s.icon;
                      const currentIdx = STAGE_KEYS.indexOf(inspectedJob.stage);
                      const isDone = inspectedJob.status === "completed" || idx < currentIdx;
                      const isActive =
                        inspectedJob.status !== "completed" &&
                        inspectedJob.status !== "failed" &&
                        s.key === inspectedJob.stage;
                      const isFailedStage = inspectedJob.status === "failed" && s.key === inspectedJob.stage;

                      return (
                        <div
                          key={s.key}
                          className={`p-3 rounded-xl border flex items-center justify-between text-xs transition-colors ${
                            isActive
                              ? "bg-primary/10 border-primary/30"
                              : isDone
                              ? "bg-emerald-500/5 border-emerald-500/20"
                              : isFailedStage
                              ? "bg-red-500/10 border-red-500/30"
                              : "bg-muted/20 border-border/30 opacity-60"
                          }`}
                        >
                          <div className="flex items-center gap-3">
                            <div
                              className={`h-7 w-7 rounded-lg flex items-center justify-center ${
                                isDone
                                  ? "bg-emerald-500/20 text-emerald-500"
                                  : isActive
                                  ? "bg-primary text-primary-foreground animate-pulse"
                                  : isFailedStage
                                  ? "bg-red-500/20 text-red-500"
                                  : "bg-muted text-muted-foreground"
                              }`}
                            >
                              <Icon className="h-4 w-4" />
                            </div>
                            <div>
                              <p className="font-semibold text-foreground">
                                {idx + 1}. {s.label}
                              </p>
                              <p className="text-[11px] text-muted-foreground">{s.desc}</p>
                            </div>
                          </div>

                          <div>
                            {isDone ? (
                              <span className="text-emerald-500 font-medium flex items-center gap-1 text-[11px]">
                                <Check className="h-3.5 w-3.5" /> Completed
                              </span>
                            ) : isActive ? (
                              <span className="text-primary font-semibold flex items-center gap-1 text-[11px] animate-pulse">
                                <Activity className="h-3.5 w-3.5" /> In Progress
                              </span>
                            ) : isFailedStage ? (
                              <span className="text-red-500 font-semibold flex items-center gap-1 text-[11px]">
                                <XCircle className="h-3.5 w-3.5" /> Failed Here
                              </span>
                            ) : (
                              <span className="text-muted-foreground/60 text-[11px]">Pending</span>
                            )}
                          </div>
                        </div>
                      );
                    })}
                  </div>

                  {/* Error Log Console */}
                  {inspectedJob.status === "failed" && inspectedJob.error_message && (
                    <div className="mt-4 rounded-xl bg-red-950/20 border border-red-500/30 p-4 space-y-2">
                      <div className="flex items-center justify-between text-xs text-red-400 font-semibold">
                        <span className="flex items-center gap-1.5">
                          <Terminal className="h-3.5 w-3.5" /> Error Diagnostics Console
                        </span>
                        <CopyPill text={inspectedJob.error_message} label="Copy Log" />
                      </div>
                      <pre className="text-[11px] font-mono text-red-300/90 whitespace-pre-wrap break-all bg-black/40 p-3 rounded-lg border border-red-500/20 leading-relaxed max-h-48 overflow-y-auto">
                        {inspectedJob.error_message}
                      </pre>
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* Pipeline Legend */}
          <div className="rounded-2xl border border-border bg-card/40 p-4 text-xs">
            <div className="flex items-center justify-between flex-wrap gap-2 mb-3">
              <div className="flex items-center gap-2">
                <Zap className="h-4 w-4 text-primary" />
                <span className="font-semibold text-foreground">Ingestion Pipeline Architecture</span>
              </div>
              <span className="text-[11px] text-muted-foreground">
                Asynchronous worker processes orchestrated via background task scheduler
              </span>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-5 gap-2.5">
              {STAGES.map((s, i) => {
                const Icon = s.icon;
                return (
                  <div key={s.key} className="p-2.5 rounded-xl bg-muted/40 border border-border/40 text-left">
                    <div className="flex items-center gap-2 mb-1 text-primary">
                      <Icon className="h-3.5 w-3.5" />
                      <span className="font-semibold text-foreground">{i + 1}. {s.label}</span>
                    </div>
                    <p className="text-[10px] text-muted-foreground leading-relaxed">{s.desc}</p>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </div>
    </AppShell>
  );
}
