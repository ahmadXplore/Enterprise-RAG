"use client";

import * as React from "react";
import {
  ScrollText,
  Search,
  Filter,
  RefreshCw,
  ShieldAlert,
  ShieldCheck,
  User,
  Clock,
  ChevronLeft,
  ChevronRight,
  Code,
  FileText,
  KeyRound,
  Trash2,
} from "lucide-react";
import { AppShell } from "@/components/layout/app-shell";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { adminApi, AuditLogItem } from "@/lib/api";
import { Spinner, EmptyState, ErrorState } from "@/components/ui/states";

export default function AuditLogsPage() {
  const [logs, setLogs] = React.useState<AuditLogItem[]>([]);
  const [total, setTotal] = React.useState(0);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);

  // Filters & Pagination
  const [search, setSearch] = React.useState("");
  const [actionFilter, setActionFilter] = React.useState("");
  const [page, setPage] = React.useState(1);
  const pageSize = 25;

  const [expandedLogId, setExpandedLogId] = React.useState<string | null>(null);

  const fetchLogs = React.useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const offset = (page - 1) * pageSize;
      const res = await adminApi.auditLogs({
        action: actionFilter || undefined,
        search: search.trim() || undefined,
        limit: pageSize,
        offset,
      });
      setLogs(res.items);
      setTotal(res.total);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load audit logs");
    } finally {
      setLoading(false);
    }
  }, [page, actionFilter, search]);

  React.useEffect(() => {
    fetchLogs();
  }, [fetchLogs]);

  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  const getActionBadge = (action: string) => {
    if (action.includes("security") || action.includes("blocked") || action.includes("malicious")) {
      return (
        <Badge className="bg-destructive/15 text-destructive border-destructive/30 font-mono text-[10px] gap-1">
          <ShieldAlert className="h-3 w-3" /> {action}
        </Badge>
      );
    }
    if (action.includes("upload") || action.includes("create")) {
      return (
        <Badge className="bg-emerald-500/15 text-emerald-700 dark:text-emerald-400 border-emerald-500/30 font-mono text-[10px] gap-1">
          <ShieldCheck className="h-3 w-3" /> {action}
        </Badge>
      );
    }
    if (action.includes("delete") || action.includes("remove")) {
      return (
        <Badge className="bg-amber-500/15 text-amber-700 dark:text-amber-400 border-amber-500/30 font-mono text-[10px] gap-1">
          <Trash2 className="h-3 w-3" /> {action}
        </Badge>
      );
    }
    if (action.includes("auth") || action.includes("login")) {
      return (
        <Badge className="bg-sky-500/15 text-sky-700 dark:text-sky-400 border-sky-500/30 font-mono text-[10px] gap-1">
          <KeyRound className="h-3 w-3" /> {action}
        </Badge>
      );
    }
    return (
      <Badge variant="outline" className="font-mono text-[10px]">
        {action}
      </Badge>
    );
  };

  return (
    <AppShell>
      <div className="p-6 max-w-7xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-2 border-b border-border">
          <div>
            <h1 className="text-xl font-bold tracking-tight text-foreground flex items-center gap-2">
              <ScrollText className="h-5 w-5 text-primary" />
              Security Audit Logs & Event Trail
            </h1>
            <p className="text-xs text-muted-foreground mt-0.5">
              Immutable ledger of privileged administrative operations, ingestion activities, and security mitigations
            </p>
          </div>

          <div className="flex items-center gap-2">
            <Badge variant="outline" className="font-mono text-xs">
              {total.toLocaleString()} Recorded Events
            </Badge>
            <Button
              variant="outline"
              size="sm"
              onClick={fetchLogs}
              disabled={loading}
              className="gap-1.5 text-xs h-8"
            >
              <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} />
              Refresh
            </Button>
          </div>
        </div>

        {/* Filters Bar */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 p-3 rounded-xl border border-border bg-card shadow-xs">
          <div className="relative sm:col-span-2">
            <Search className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
            <input
              type="text"
              placeholder="Search by action, resource type, or details..."
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                setPage(1);
              }}
              className="w-full pl-9 pr-3 py-1.5 rounded-lg border border-input bg-background text-xs placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
            />
          </div>

          <div className="flex items-center gap-2">
            <Filter className="h-4 w-4 text-muted-foreground shrink-0" />
            <select
              value={actionFilter}
              onChange={(e) => {
                setActionFilter(e.target.value);
                setPage(1);
              }}
              className="w-full h-8 rounded-lg border border-input bg-background px-2.5 text-xs text-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
            >
              <option value="">All Actions</option>
              <option value="document:upload">document:upload</option>
              <option value="document:create">document:create</option>
              <option value="document:delete">document:delete</option>
              <option value="security:malicious_file_blocked">security:malicious_file_blocked</option>
              <option value="auth:login">auth:login</option>
              <option value="user:create">user:create</option>
            </select>
          </div>
        </div>

        {/* Audit Logs Table */}
        <Card className="border-border bg-card shadow-xs">
          <CardContent className="p-0 overflow-x-auto">
            {loading && logs.length === 0 ? (
              <div className="py-20 flex flex-col items-center justify-center gap-3">
                <Spinner className="h-8 w-8" />
                <span className="text-xs text-muted-foreground">Fetching audit log ledger...</span>
              </div>
            ) : error ? (
              <div className="p-6">
                <ErrorState message={error} onRetry={fetchLogs} />
              </div>
            ) : logs.length === 0 ? (
              <div className="py-16 text-center">
                <EmptyState
                  title="No Audit Logs Found"
                  description="No audit events matched your search or action filter."
                />
              </div>
            ) : (
              <table className="w-full text-xs text-left border-collapse">
                <thead>
                  <tr className="border-b border-border bg-muted/40 text-muted-foreground font-semibold">
                    <th className="py-2.5 px-4">Timestamp</th>
                    <th className="py-2.5 px-4">Actor</th>
                    <th className="py-2.5 px-4">Action</th>
                    <th className="py-2.5 px-4">Resource</th>
                    <th className="py-2.5 px-4 font-mono">Client IP (Hashed)</th>
                    <th className="py-2.5 px-4 text-right">Details</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border/60">
                  {logs.map((log) => {
                    const isExpanded = expandedLogId === log.id;
                    return (
                      <React.Fragment key={log.id}>
                        <tr className="hover:bg-accent/40 transition-colors">
                          <td className="py-3 px-4 text-foreground/80 font-mono text-[11px] whitespace-nowrap">
                            {new Date(log.created_at).toLocaleString()}
                          </td>
                          <td className="py-3 px-4 font-medium text-foreground">
                            <div className="flex items-center gap-1.5">
                              <User className="h-3.5 w-3.5 text-muted-foreground" />
                              <span>{log.user_email}</span>
                            </div>
                          </td>
                          <td className="py-3 px-4">{getActionBadge(log.action)}</td>
                          <td className="py-3 px-4">
                            <span className="font-medium text-foreground capitalize">
                              {log.resource_type}
                            </span>
                            {log.resource_id && (
                              <span className="text-muted-foreground font-mono text-[10px] ml-1.5">
                                ({log.resource_id.slice(0, 8)}...)
                              </span>
                            )}
                          </td>
                          <td className="py-3 px-4 font-mono text-[10px] text-muted-foreground">
                            {log.ip_hash ? `${log.ip_hash.slice(0, 14)}...` : "—"}
                          </td>
                          <td className="py-3 px-4 text-right">
                            {log.metadata && Object.keys(log.metadata).length > 0 ? (
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => setExpandedLogId(isExpanded ? null : log.id)}
                                className="h-7 text-xs px-2 gap-1 text-primary hover:bg-primary/10"
                              >
                                <Code className="h-3 w-3" />
                                <span>{isExpanded ? "Hide JSON" : "View"}</span>
                              </Button>
                            ) : (
                              <span className="text-muted-foreground text-[11px]">—</span>
                            )}
                          </td>
                        </tr>
                        {isExpanded && log.metadata && (
                          <tr className="bg-muted/30">
                            <td colSpan={6} className="p-3 px-6">
                              <div className="rounded-lg border border-border bg-card p-3 font-mono text-[11px] text-foreground/90 overflow-x-auto shadow-inner">
                                <pre>{JSON.stringify(log.metadata, null, 2)}</pre>
                              </div>
                            </td>
                          </tr>
                        )}
                      </React.Fragment>
                    );
                  })}
                </tbody>
              </table>
            )}
          </CardContent>
        </Card>

        {/* Pagination Bar */}
        {total > pageSize && (
          <div className="flex items-center justify-between text-xs text-muted-foreground pt-1">
            <span>
              Showing {(page - 1) * pageSize + 1}–{Math.min(page * pageSize, total)} of {total} records
            </span>
            <div className="flex items-center gap-1.5">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page <= 1}
                className="h-8 px-2.5 gap-1"
              >
                <ChevronLeft className="h-3.5 w-3.5" /> Previous
              </Button>
              <span className="font-mono px-2 font-medium text-foreground">
                Page {page} of {totalPages}
              </span>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={page >= totalPages}
                className="h-8 px-2.5 gap-1"
              >
                Next <ChevronRight className="h-3.5 w-3.5" />
              </Button>
            </div>
          </div>
        )}
      </div>
    </AppShell>
  );
}
