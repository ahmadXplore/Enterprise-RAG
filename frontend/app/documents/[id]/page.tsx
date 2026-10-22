"use client";

import * as React from "react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import {
  ArrowLeft,
  FileText,
  Layers,
  Bookmark,
  Hash,
  Play,
  Clock,
  CheckCircle2,
  Table as TableIcon,
  Search,
  Copy,
  Check,
  Target,
  Sparkles,
  ExternalLink,
  ChevronDown,
  Trash2,
} from "lucide-react";
import { AppShell } from "@/components/layout/app-shell";
import { SectionTree } from "@/components/documents/section-tree";
import { EvidenceDrawer } from "@/components/citations/evidence-drawer";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Spinner, ErrorState, EmptyState } from "@/components/ui/states";
import { documentsApi } from "@/lib/api";
import { DocumentDetailRead, DocumentSectionRead, DocumentChunkRead } from "@/lib/types";
import { isAdmin } from "@/lib/auth";
import DOMPurify from "isomorphic-dompurify";
import { useModal } from "@/components/ui/modal-context";

function DocumentDetailContent() {
  const modal = useModal();
  const params = useParams();
  const searchParams = useSearchParams();
  const router = useRouter();

  const id = Array.isArray(params.id) ? params.id[0] : params.id;
  const initialTargetChunk = searchParams.get("chunk");

  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);
  const [doc, setDoc] = React.useState<DocumentDetailRead | null>(null);
  const [sections, setSections] = React.useState<DocumentSectionRead[]>([]);
  const [chunks, setChunks] = React.useState<DocumentChunkRead[]>([]);
  const [selectedSection, setSelectedSection] = React.useState<DocumentSectionRead | null>(null);

  // In-document chunk search & filtering
  const [searchFilter, setSearchFilter] = React.useState("");
  const [targetChunkId, setTargetChunkId] = React.useState<string | null>(initialTargetChunk);
  const [copiedChunkId, setCopiedChunkId] = React.useState<string | null>(null);
  const [loadingMore, setLoadingMore] = React.useState(false);
  const [expandedChunkIds, setExpandedChunkIds] = React.useState<Set<string>>(new Set());

  const toggleExpanded = (chunkId: string) => {
    setExpandedChunkIds((prev) => {
      const next = new Set(prev);
      if (next.has(chunkId)) next.delete(chunkId);
      else next.add(chunkId);
      return next;
    });
  };

  // Evidence drawer state
  const [activeChunkId, setActiveChunkId] = React.useState<string | null>(null);
  const [isDrawerOpen, setIsDrawerOpen] = React.useState(false);
  const [isIngesting, setIsIngesting] = React.useState(false);

  const chunkRefs = React.useRef<{ [key: string]: HTMLDivElement | null }>({});
  const admin = isAdmin();

  const loadData = React.useCallback(async () => {
    if (!id) return;
    setLoading(true);
    setError(null);
    try {
      const [detailRes, sectionsRes, chunksRes] = await Promise.allSettled([
        documentsApi.get(id),
        documentsApi.getSections(id),
        documentsApi.getChunks(id, 100),
      ]);

      if (detailRes.status === "fulfilled") {
        setDoc(detailRes.value);
      } else {
        throw new Error(detailRes.reason?.message || "Failed to load document details");
      }

      if (sectionsRes.status === "fulfilled") {
        setSections(sectionsRes.value);
      }

      let loadedChunks: DocumentChunkRead[] = [];
      if (chunksRes.status === "fulfilled") {
        loadedChunks = chunksRes.value;
      }

      // If a target chunk ID is specified from URL and not in first 100, fetch it directly
      if (initialTargetChunk && !loadedChunks.some((c) => c.id === initialTargetChunk)) {
        try {
          const targetChunk = await documentsApi.getChunk(initialTargetChunk);
          if (targetChunk) {
            loadedChunks = [targetChunk, ...loadedChunks];
          }
        } catch {
          // If chunk lookup fails, keep standard chunks
        }
      }

      setChunks(loadedChunks);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Error fetching document data");
    } finally {
      setLoading(false);
    }
  }, [id, initialTargetChunk]);

  React.useEffect(() => {
    loadData();
  }, [loadData]);

  // Smooth scroll to targeted chunk once rendered
  React.useEffect(() => {
    if (!targetChunkId || loading) return;
    const timer = setTimeout(() => {
      const el = chunkRefs.current[targetChunkId];
      if (el) {
        el.scrollIntoView({ behavior: "smooth", block: "center" });
      }
    }, 250);
    return () => clearTimeout(timer);
  }, [targetChunkId, loading, chunks]);

  const handleLoadMoreChunks = async () => {
    if (!id) return;
    setLoadingMore(true);
    try {
      const nextBatch = await documentsApi.getChunks(id, 100, chunks.length);
      if (nextBatch.length > 0) {
        setChunks((prev) => {
          const existingIds = new Set(prev.map((c) => c.id));
          const newChunks = nextBatch.filter((c) => !existingIds.has(c.id));
          return [...prev, ...newChunks];
        });
      }
    } catch (err) {
      console.error("Failed to load more chunks", err);
    } finally {
      setLoadingMore(false);
    }
  };

  const handleIngest = async () => {
    if (!id) return;
    setIsIngesting(true);
    try {
      await documentsApi.ingest(id);
      modal.toast.success("Document ingestion pipeline started in the background.");
      await loadData();
    } catch (err: unknown) {
      modal.toast.error(err instanceof Error ? err.message : "Failed to trigger ingestion");
    } finally {
      setIsIngesting(false);
    }
  };

  const handleDelete = async () => {
    if (!id || !doc) return;
    const confirmed = await modal.confirm({
      title: "Confirm Document Deletion",
      message: (
        <span>
          Are you sure you want to permanently delete{" "}
          <strong className="text-foreground">{doc.title || "this document"}</strong> from the corpus?
          All extracted sections, text chunks, and vector index embeddings in Qdrant will be removed.
        </span>
      ),
      confirmText: "Delete Document",
      variant: "destructive",
    });
    if (!confirmed) return;

    try {
      await documentsApi.delete(id);
      modal.toast.success("Document deleted successfully.");
      router.push("/documents");
    } catch (err: unknown) {
      modal.toast.error(err instanceof Error ? err.message : "Deletion failed");
    }
  };

  const openEvidence = (chunkId: string) => {
    setActiveChunkId(chunkId);
    setIsDrawerOpen(true);
  };

  const copyChunkContent = (chunk: DocumentChunkRead) => {
    navigator.clipboard.writeText(chunk.text);
    setCopiedChunkId(chunk.id);
    setTimeout(() => setCopiedChunkId(null), 2000);
  };

  const handleSelectSection = (sec: DocumentSectionRead) => {
    setSelectedSection(sec);
    // Find the first matching chunk and auto-scroll to it
    const headingLower = (sec.heading || "").toLowerCase();
    const matching = chunks.find((c) => {
      if (sec.page_start !== null && c.page_start !== null) {
        return c.page_start >= (sec.page_start ?? 0) && c.page_start <= (sec.page_end ?? 9999);
      }
      return (
        (c.heading_path && c.heading_path.toLowerCase().includes(headingLower)) ||
        c.text.toLowerCase().includes(headingLower)
      );
    });

    if (matching) {
      setTargetChunkId(matching.id);
    }
  };

  // Universal Filter: Section bounds + Section text match + In-document keyword search
  const displayedChunks = React.useMemo(() => {
    let result = chunks;

    if (selectedSection) {
      const headingLower = (selectedSection.heading || "").toLowerCase().trim();
      const hasPageBounds = selectedSection.page_start !== null;

      result = result.filter((c) => {
        // Page bounds matching if available
        if (hasPageBounds && c.page_start !== null) {
          return (
            c.page_start >= (selectedSection.page_start ?? 0) &&
            c.page_start <= (selectedSection.page_end ?? 9999)
          );
        }
        // Universal text / heading matching for research papers, datasets, and reports
        if (headingLower) {
          const pathMatch = c.heading_path && c.heading_path.toLowerCase().includes(headingLower);
          const textMatch = c.text.toLowerCase().includes(headingLower);
          return pathMatch || textMatch;
        }
        return true;
      });
    }

    if (searchFilter.trim()) {
      const q = searchFilter.toLowerCase().trim();
      result = result.filter(
        (c) =>
          c.text.toLowerCase().includes(q) ||
          (c.heading_path && c.heading_path.toLowerCase().includes(q)) ||
          c.id.toLowerCase().includes(q) ||
          String(c.chunk_index) === q
      );
    }

    return result;
  }, [chunks, selectedSection, searchFilter]);

  return (
    <AppShell>
      <div className="p-6 max-w-7xl mx-auto space-y-6">
        {/* Navigation & Actions */}
        <div className="flex items-center justify-between">
          <Link
            href="/documents"
            className="text-xs text-muted-foreground hover:text-foreground inline-flex items-center gap-1.5 transition-colors"
          >
            <ArrowLeft className="h-3.5 w-3.5" /> Back to Document Library
          </Link>

          {admin && (
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={handleIngest}
                disabled={isIngesting || doc?.status === "ready"}
                className="gap-1.5 text-xs"
              >
                {isIngesting ? (
                  <>
                    <Clock className="h-3.5 w-3.5 animate-spin" /> Ingesting...
                  </>
                ) : (
                  <>
                    <Play className="h-3.5 w-3.5" /> Ingest / Re-index
                  </>
                )}
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={handleDelete}
                className="gap-1.5 text-xs text-destructive hover:bg-destructive/10 hover:text-destructive border-border"
                title="Permanently delete document"
              >
                <Trash2 className="h-3.5 w-3.5" /> Delete Document
              </Button>
            </div>
          )}
        </div>

        {loading ? (
          <div className="py-24 flex justify-center">
            <Spinner className="h-8 w-8" />
          </div>
        ) : error ? (
          <ErrorState message={error} onRetry={loadData} />
        ) : !doc ? (
          <EmptyState title="Document not found" />
        ) : (
          <div className="space-y-6">
            {/* Document Header Card */}
            <Card className="p-6 border-border bg-card">
              <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div className="space-y-1">
                  <div className="flex items-center gap-2 flex-wrap">
                    <FileText className="h-5 w-5 text-primary shrink-0" />
                    <h1 className="text-lg font-bold tracking-tight text-foreground">{doc.title}</h1>
                    <Badge variant={doc.status === "ready" ? "success" : "secondary"}>
                      {doc.status}
                    </Badge>
                    {targetChunkId && (
                      <Badge variant="outline" className="text-xs text-primary border-primary/40 gap-1 font-mono">
                        <Target className="h-3 w-3" /> Target Chunk Focused
                      </Badge>
                    )}
                  </div>
                  <div className="text-xs text-muted-foreground flex flex-wrap gap-4 pt-1">
                    {doc.organization && <span>Company: {doc.organization}</span>}
                    {doc.report_year && <span>Year: {doc.report_year}</span>}
                    <span>Type: {doc.document_type}</span>
                    <span>Pages: {doc.page_count ?? "—"}</span>
                    <span>Chunks: {doc.chunk_count ?? chunks.length}</span>
                  </div>
                </div>
              </div>
            </Card>

            {/* Target Chunk Notification Banner */}
            {targetChunkId && (
              <div className="p-3.5 rounded-lg border border-primary/30 bg-primary/10 flex items-center justify-between gap-4">
                <div className="flex items-center gap-2.5 text-xs text-foreground">
                  <Sparkles className="h-4 w-4 text-primary shrink-0" />
                  <span>
                    Viewing targeted evidence chunk: <strong className="font-mono text-primary">{targetChunkId.slice(0, 8)}...</strong>
                  </span>
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setTargetChunkId(null)}
                  className="h-7 text-xs px-2.5 text-muted-foreground hover:text-foreground"
                >
                  Clear target focus
                </Button>
              </div>
            )}

            {/* Main Inspection Grid (Section Tree + Chunks) */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              {/* Left Column: Section Hierarchy Tree */}
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <h2 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider flex items-center gap-1.5">
                    <Layers className="h-3.5 w-3.5 text-primary" />
                    Section Tree Hierarchy ({sections.length})
                  </h2>
                  {selectedSection && (
                    <button
                      onClick={() => setSelectedSection(null)}
                      className="text-[11px] text-primary hover:underline"
                    >
                      Clear filter
                    </button>
                  )}
                </div>

                <div className="rounded-lg border border-border bg-card p-3 max-h-[650px] overflow-y-auto">
                  <SectionTree
                    sections={sections}
                    selectedSectionId={selectedSection?.id}
                    onSelectSection={handleSelectSection}
                  />
                </div>
              </div>

              {/* Right Column: Chunk Context & Evidence Previews */}
              <div className="lg:col-span-2 space-y-3">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                  <h2 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider flex items-center gap-1.5">
                    <Bookmark className="h-3.5 w-3.5 text-emerald-400" />
                    Indexed Document Chunks ({displayedChunks.length} of {doc.chunk_count ?? chunks.length})
                  </h2>

                  {selectedSection && (
                    <span className="text-xs text-primary font-mono truncate max-w-xs">
                      Filtered: {selectedSection.heading}
                    </span>
                  )}
                </div>

                {/* In-Document Search Bar */}
                <div className="relative">
                  <Search className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
                  <input
                    type="text"
                    value={searchFilter}
                    onChange={(e) => setSearchFilter(e.target.value)}
                    placeholder="Search within this document (e.g. Risk Factors, Indemnification, Revenue)..."
                    className="w-full pl-9 pr-4 py-1.5 text-xs rounded-md border border-border bg-card text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary"
                  />
                  {searchFilter && (
                    <button
                      onClick={() => setSearchFilter("")}
                      className="absolute right-3 top-2 text-xs text-muted-foreground hover:text-foreground"
                    >
                      ✕
                    </button>
                  )}
                </div>

                {displayedChunks.length === 0 ? (
                  <div className="rounded-lg border border-border bg-card p-8 text-center text-xs text-muted-foreground space-y-2">
                    <p>No chunks match the current filter or search criteria.</p>
                    {(selectedSection || searchFilter) && (
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => {
                          setSelectedSection(null);
                          setSearchFilter("");
                        }}
                        className="text-xs h-7"
                      >
                        Reset filters
                      </Button>
                    )}
                  </div>
                ) : (
                  <div className="space-y-3 max-h-[650px] overflow-y-auto pr-1">
                    {displayedChunks.map((chunk) => {
                      const isTarget = targetChunkId === chunk.id;
                      const isExpanded = expandedChunkIds.has(chunk.id);
                      const PREVIEW_LIMIT = 300;
                      const hasMoreText = !chunk.table_html && chunk.text.length > PREVIEW_LIMIT;

                      return (
                        <div
                          key={chunk.id}
                          ref={(el) => {
                            chunkRefs.current[chunk.id] = el;
                          }}
                          className={`rounded-lg border p-4 space-y-2.5 transition-all duration-300 ${
                            isTarget
                              ? "border-primary bg-primary/5 shadow-md shadow-primary/10 ring-2 ring-primary/40"
                              : "border-border bg-card hover:border-primary/40"
                          }`}
                        >
                          {/* Header row */}
                          <div className="flex items-center justify-between text-xs">
                            <div className="flex items-center gap-2 flex-wrap">
                              <span className="font-mono text-muted-foreground font-semibold">
                                #{chunk.chunk_index}
                              </span>
                              {isTarget && (
                                <Badge variant="default" className="text-[10px] bg-primary text-primary-foreground gap-1 py-0">
                                  <Target className="h-3 w-3" /> Target Evidence
                                </Badge>
                              )}
                              {chunk.page_start !== null && (
                                <Badge variant="outline" className="text-[10px]">
                                  Page {chunk.page_start}
                                </Badge>
                              )}
                              {chunk.chunk_type && (
                                <Badge variant="secondary" className="text-[10px] uppercase">
                                  {chunk.chunk_type}
                                </Badge>
                              )}
                            </div>

                            <div className="flex items-center gap-1.5">
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => copyChunkContent(chunk)}
                                className="h-6 text-[11px] px-2 text-muted-foreground hover:text-foreground"
                                title="Copy chunk text"
                              >
                                {copiedChunkId === chunk.id ? (
                                  <Check className="h-3 w-3 text-emerald-400" />
                                ) : (
                                  <Copy className="h-3 w-3" />
                                )}
                              </Button>
                              <Button
                                variant={isTarget ? "default" : "ghost"}
                                size="sm"
                                onClick={() => openEvidence(chunk.id)}
                                className={`h-6 text-[11px] px-2.5 gap-1 ${
                                  isTarget
                                    ? "bg-primary text-primary-foreground hover:bg-primary/90"
                                    : "text-primary hover:text-primary hover:bg-primary/10"
                                }`}
                              >
                                <CheckCircle2 className="h-3 w-3" />
                                <span>{isTarget ? "Read & Verify" : "Evidence Drawer"}</span>
                              </Button>
                            </div>
                          </div>

                          {/* Section path */}
                          {chunk.heading_path && (
                            <div className="text-[11px] font-mono text-muted-foreground truncate bg-muted/50 px-2 py-0.5 rounded border border-border/40">
                              Section: {chunk.heading_path}
                            </div>
                          )}

                          {/* Content */}
                          {chunk.table_html ? (
                            <div className="rounded border border-border/80 bg-muted/50 p-2.5 text-xs overflow-x-auto space-y-2">
                              <div className="text-[10px] text-muted-foreground font-semibold flex items-center justify-between gap-1">
                                <span className="flex items-center gap-1">
                                  <TableIcon className="h-3 w-3 text-primary" /> Structured Table (HTML)
                                </span>
                                {!isExpanded && (
                                  <button
                                    onClick={() => toggleExpanded(chunk.id)}
                                    className="text-primary hover:underline text-[10px]"
                                  >
                                    Expand full table ↓
                                  </button>
                                )}
                              </div>
                              <div
                                className={isExpanded ? "" : "max-h-32 overflow-hidden"}
                                dangerouslySetInnerHTML={{
                                  __html: DOMPurify.sanitize(chunk.table_html, {
                                    ALLOWED_TAGS: [
                                      "table", "thead", "tbody", "tfoot", "tr", "th", "td",
                                      "caption", "colgroup", "col", "span", "div", "b", "i",
                                      "strong", "em", "p",
                                    ],
                                    ALLOWED_ATTR: ["class", "id", "style", "colspan", "rowspan", "scope"],
                                  }),
                                }}
                              />

                              {/* Always show raw text extraction for full readability */}
                              {isExpanded && chunk.text && (
                                <div className="border-t border-border/40 pt-2 space-y-1">
                                  <div className="text-[10px] text-primary font-semibold flex items-center gap-1">
                                    <FileText className="h-3 w-3" /> Full Extracted Text
                                  </div>
                                  <p className="text-xs text-foreground leading-relaxed whitespace-pre-wrap font-sans">
                                    {chunk.text}
                                  </p>
                                </div>
                              )}

                              <div className="pt-1 border-t border-border/30 text-center">
                                <button
                                  onClick={() => toggleExpanded(chunk.id)}
                                  className={`text-[10px] hover:underline ${isExpanded ? "text-muted-foreground hover:text-foreground" : "text-primary"}`}
                                >
                                  {isExpanded ? "↑ Collapse" : "↓ Show full table + text"}
                                </button>
                              </div>
                            </div>
                          ) : (
                            <div className="space-y-1">
                              <p className="text-xs text-foreground leading-relaxed font-sans whitespace-pre-wrap">
                                {isExpanded || !hasMoreText
                                  ? chunk.text
                                  : chunk.text.slice(0, PREVIEW_LIMIT) + "…"}
                              </p>
                              {hasMoreText && (
                                <button
                                  onClick={() => toggleExpanded(chunk.id)}
                                  className={`text-[11px] font-medium transition-colors ${
                                    isExpanded
                                      ? "text-muted-foreground hover:text-foreground"
                                      : "text-primary hover:text-primary/80"
                                  }`}
                                >
                                  {isExpanded
                                    ? "↑ Show less"
                                    : `↓ Read full content (${chunk.text.length} chars)`}
                                </button>
                              )}
                            </div>
                          )}
                        </div>
                      );
                    })}

                    {/* Pagination / Load More Chunks */}
                    {chunks.length < (doc.chunk_count ?? chunks.length) && (
                      <div className="pt-2 flex justify-center">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={handleLoadMoreChunks}
                          disabled={loadingMore}
                          className="text-xs gap-1.5"
                        >
                          {loadingMore ? (
                            <>
                              <Clock className="h-3.5 w-3.5 animate-spin" /> Loading more chunks...
                            </>
                          ) : (
                            <>
                              <ChevronDown className="h-3.5 w-3.5" /> Load More Chunks (Currently {chunks.length} of {doc.chunk_count})
                            </>
                          )}
                        </Button>
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Phase 15 Evidence Drawer */}
        <EvidenceDrawer
          isOpen={isDrawerOpen}
          onClose={() => setIsDrawerOpen(false)}
          chunkId={activeChunkId}
          documentId={id}
        />
      </div>
    </AppShell>
  );
}

export default function DocumentDetailPage() {
  return (
    <React.Suspense
      fallback={
        <AppShell>
          <div className="py-24 flex justify-center">
            <Spinner className="h-8 w-8" />
          </div>
        </AppShell>
      }
    >
      <DocumentDetailContent />
    </React.Suspense>
  );
}
