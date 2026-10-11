"use client";

import * as React from "react";
import { Plus, Search, RefreshCw, FileText } from "lucide-react";
import { AppShell } from "@/components/layout/app-shell";
import { DocumentTable } from "@/components/documents/document-table";
import { UploadModal } from "@/components/documents/upload-modal";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Spinner, EmptyState, ErrorState } from "@/components/ui/states";
import { documentsApi } from "@/lib/api";
import { DocumentRead, PaginatedResponse } from "@/lib/types";
import { isAdmin } from "@/lib/auth";

export default function DocumentsPage() {
  const [data, setData] = React.useState<PaginatedResponse<DocumentRead> | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);
  const [page, setPage] = React.useState(1);
  const [company, setCompany] = React.useState("");
  const [year, setYear] = React.useState<string>("");
  const [statusFilter, setStatusFilter] = React.useState<string>("");
  const [isModalOpen, setIsModalOpen] = React.useState(false);
  const [ingestingIds, setIngestingIds] = React.useState<Set<string>>(new Set());

  const admin = isAdmin();

  const fetchDocuments = React.useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await documentsApi.list({
        page,
        page_size: 15,
        company: company || undefined,
        year: year ? parseInt(year, 10) : undefined,
        status: statusFilter || undefined,
      });
      setData(res);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load documents");
    } finally {
      setLoading(false);
    }
  }, [page, company, year, statusFilter]);

  React.useEffect(() => {
    fetchDocuments();
  }, [fetchDocuments]);

  const handleIngest = async (docId: string) => {
    setIngestingIds((prev) => new Set(prev).add(docId));
    try {
      await documentsApi.ingest(docId);
      // Refresh list
      await fetchDocuments();
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Failed to start ingestion job");
    } finally {
      setIngestingIds((prev) => {
        const next = new Set(prev);
        next.delete(docId);
        return next;
      });
    }
  };

  return (
    <AppShell>
      <div className="p-6 max-w-7xl mx-auto space-y-6">
        {/* Header & Actions */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <h1 className="text-xl font-bold tracking-tight text-foreground flex items-center gap-2">
              <FileText className="h-5 w-5 text-primary" />
              Document Library
            </h1>
            <p className="text-xs text-muted-foreground mt-0.5">
              Academic research papers, educational datasets, spreadsheets, and syllabi indexed for hybrid retrieval
            </p>
          </div>

          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" onClick={() => fetchDocuments()} className="gap-1 text-xs">
              <RefreshCw className="h-3.5 w-3.5" /> Refresh
            </Button>
            {admin && (
              <Button size="sm" onClick={() => setIsModalOpen(true)} className="gap-1 text-xs">
                <Plus className="h-3.5 w-3.5" /> Register Document
              </Button>
            )}
          </div>
        </div>

        {/* Filters */}
        <div className="grid grid-cols-1 sm:grid-cols-4 gap-3 p-3 rounded-lg border border-border bg-card">
          <Input
            placeholder="Filter by institution / organization..."
            value={company}
            onChange={(e) => {
              setCompany(e.target.value);
              setPage(1);
            }}
            className="h-8 text-xs"
          />
          <Input
            placeholder="Filter by year (e.g. 2025)..."
            value={year}
            onChange={(e) => {
              setYear(e.target.value);
              setPage(1);
            }}
            className="h-8 text-xs"
          />
          <select
            value={statusFilter}
            onChange={(e) => {
              setStatusFilter(e.target.value);
              setPage(1);
            }}
            aria-label="Filter documents by status"
            className="h-8 rounded-md border border-input bg-card px-2 text-xs text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <option value="">All Statuses</option>
            <option value="registered">Registered</option>
            <option value="pending">Pending</option>
            <option value="parsing">Parsing</option>
            <option value="embedding">Embedding</option>
            <option value="ready">Ready (Indexed)</option>
            <option value="failed">Failed</option>
          </select>
          {(company || year || statusFilter) && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                setCompany("");
                setYear("");
                setStatusFilter("");
                setPage(1);
              }}
              className="h-8 text-xs text-muted-foreground hover:text-foreground"
            >
              Clear filters
            </Button>
          )}
        </div>

        {/* Content Table / States */}
        {loading ? (
          <div className="py-20 flex justify-center">
            <Spinner className="h-8 w-8" />
          </div>
        ) : error ? (
          <ErrorState message={error} onRetry={fetchDocuments} />
        ) : !data || data.items.length === 0 ? (
          <EmptyState
            title="No documents found"
            description={
              company || year || statusFilter
                ? "No documents match your active filter criteria."
                : "No documents have been registered into the repository yet."
            }
          />
        ) : (
          <div className="space-y-4">
            <DocumentTable
              documents={data.items}
              onIngest={handleIngest}
              ingestingIds={ingestingIds}
            />

            {/* Pagination Controls */}
            {data.pages > 1 && (
              <div className="flex items-center justify-between text-xs text-muted-foreground pt-2">
                <span>
                  Showing page {data.page} of {data.pages} ({data.total} total items)
                </span>
                <div className="flex gap-1">
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={data.page <= 1}
                    onClick={() => setPage((p) => Math.max(1, p - 1))}
                    className="h-7 text-xs px-2.5"
                  >
                    Previous
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={data.page >= data.pages}
                    onClick={() => setPage((p) => p + 1)}
                    className="h-7 text-xs px-2.5"
                  >
                    Next
                  </Button>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Registration Modal */}
        <UploadModal
          isOpen={isModalOpen}
          onClose={() => setIsModalOpen(false)}
          onSuccess={fetchDocuments}
        />
      </div>
    </AppShell>
  );
}
