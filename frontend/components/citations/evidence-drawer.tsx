"use client";

import * as React from "react";
import { X, ExternalLink, FileText, Bookmark, Hash, Layers, CheckCircle2 } from "lucide-react";
import { Badge } from "@/lib/../components/ui/badge";
import { Button } from "@/lib/../components/ui/button";
import { documentsApi } from "@/lib/api";
import { DocumentChunkRead, DocumentDetailRead } from "@/lib/types";
import { Spinner } from "@/lib/../components/ui/states";

import DOMPurify from "isomorphic-dompurify";

export interface EvidenceDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  chunkId: string | null;
  documentId?: string | null;
  citationLabel?: string | null;
  evidenceText?: string | null;
  page?: number | null;
  section?: string | null;
}

export function EvidenceDrawer({
  isOpen,
  onClose,
  chunkId,
  documentId,
  citationLabel,
  evidenceText,
  page,
  section,
}: EvidenceDrawerProps) {
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [chunkDetail, setChunkDetail] = React.useState<DocumentChunkRead | null>(null);
  const [docDetail, setDocDetail] = React.useState<DocumentDetailRead | null>(null);

  React.useEffect(() => {
    if (!isOpen || !chunkId) {
      setChunkDetail(null);
      setDocDetail(null);
      return;
    }

    let isMounted = true;
    setLoading(true);
    setError(null);

    // Fetch chunk and document details
    documentsApi
      .getChunk(chunkId)
      .then((chunk) => {
        if (!isMounted) return;
        setChunkDetail(chunk);
        const resolvedDocId = documentId;
        if (resolvedDocId) {
          return documentsApi.get(resolvedDocId).then((doc) => {
            if (isMounted) setDocDetail(doc);
          });
        }
      })
      .catch((err) => {
        if (!isMounted) return;
        // Fallback: If chunk isn't loaded from DB or network error, we still display the passed evidence text
        setError(err.message ?? "Could not load full chunk context from server");
      })
      .finally(() => {
        if (isMounted) setLoading(false);
      });

    return () => {
      isMounted = false;
    };
  }, [isOpen, chunkId, documentId]);

  const sanitizedTableHtml = React.useMemo(() => {
    const raw = chunkDetail?.table_html;
    if (!raw) return null;
    return DOMPurify.sanitize(raw, {
      ALLOWED_TAGS: [
        "table",
        "thead",
        "tbody",
        "tfoot",
        "tr",
        "th",
        "td",
        "caption",
        "colgroup",
        "col",
        "span",
        "div",
        "b",
        "i",
        "strong",
        "em",
        "p",
      ],
      ALLOWED_ATTR: ["class", "id", "style", "colspan", "rowspan", "scope"],
    });
  }, [chunkDetail?.table_html]);

  // Auto-detect section heading from text if metadata is empty (hook must be called unconditionally)
  const inferredSection = React.useMemo(() => {
    if (section && section !== "Section details unavailable") return section;
    if (chunkDetail?.heading_path) return chunkDetail.heading_path;
    const txt = (chunkDetail?.text ?? evidenceText ?? "").trim();
    if (!txt) return null;
    const match = txt.match(/^(?:ITEM\s+[0-9]+[A-Z]?|SECTION\s+[0-9]+(?:\.[0-9]+)*|ARTICLE\s+[IVXLCDM0-9]+|CLAUSE\s+[0-9]+)[.:\s\-\u2013\u2014]+[^\n\r.]{2,80}/i);
    if (match) return match[0].trim();
    const firstLine = txt.split("\n")[0].trim();
    if (firstLine.length >= 3 && firstLine.length <= 60 && (firstLine === firstLine.toUpperCase() || /^([A-Z][A-Za-z0-9,.\-']+\s*){1,8}$/.test(firstLine))) {
      return firstLine;
    }
    return null;
  }, [section, chunkDetail?.heading_path, chunkDetail?.text, evidenceText]);

  if (!isOpen) return null;

  const resolvedSection = inferredSection || "Section provenance available in document";
  const resolvedPage = page ?? chunkDetail?.page_start ?? null;
  const fullText = chunkDetail?.text ?? evidenceText ?? "";
  const resolvedDocId = documentId || (chunkDetail as any)?.document_id;
  const docViewerUrl = resolvedDocId && chunkId ? `/documents/${resolvedDocId}?chunk=${chunkId}` : resolvedDocId ? `/documents/${resolvedDocId}` : null;

  // Highlight snippet within full text if evidence text is provided
  const renderHighlightedContent = () => {
    if (sanitizedTableHtml) {
      return (
        <div className="space-y-3">
          {/* Structured Table HTML */}
          <div className="rounded border border-border bg-muted/50 p-3 overflow-x-auto text-xs">
            <div className="text-xs font-semibold text-muted-foreground mb-2 flex items-center gap-1.5">
              <Layers className="h-3.5 w-3.5" /> Structured Table (HTML)
            </div>
            <div
              dangerouslySetInnerHTML={{
                __html: sanitizedTableHtml,
              }}
            />
          </div>

          {/* Always show raw text extraction so user can read the full content */}
          {fullText && (
            <div className="rounded border border-primary/20 bg-primary/5 p-3 space-y-1.5">
              <div className="text-xs font-semibold text-primary flex items-center gap-1.5">
                <FileText className="h-3.5 w-3.5" /> Full Extracted Text Content
              </div>
              <p className="text-xs text-foreground leading-relaxed whitespace-pre-wrap font-sans">
                {fullText}
              </p>
            </div>
          )}
        </div>
      );
    }

    if (!fullText) {
      return <p className="text-sm text-muted-foreground italic">No evidence text available.</p>;
    }

    if (!evidenceText || evidenceText.length < 5) {
      return (
        <p className="text-sm leading-relaxed text-foreground whitespace-pre-wrap font-sans">
          {fullText}
        </p>
      );
    }

    // Try highlighting the matching substring
    const lowerFull = fullText.toLowerCase();
    const lowerSnippet = evidenceText.toLowerCase().trim();
    const matchIdx = lowerFull.indexOf(lowerSnippet);

    if (matchIdx !== -1) {
      const before = fullText.slice(0, matchIdx);
      const match = fullText.slice(matchIdx, matchIdx + evidenceText.length);
      const after = fullText.slice(matchIdx + evidenceText.length);
      return (
        <p className="text-sm leading-relaxed text-foreground whitespace-pre-wrap font-sans">
          {before}
          <mark className="bg-amber-200/90 text-amber-950 px-1 py-0.5 rounded border border-amber-400 font-semibold">
            {match}
          </mark>
          {after}
        </p>
      );
    }

    return (
      <div className="space-y-3">
        {evidenceText && (
          <div className="p-2.5 rounded border border-primary/30 bg-primary/10">
            <div className="text-xs font-semibold text-primary mb-1">Exact Cited Evidence:</div>
            <p className="text-sm text-foreground italic font-medium">“{evidenceText}”</p>
          </div>
        )}
        <div className="text-xs font-semibold text-muted-foreground">Full Chunk Content:</div>
        <p className="text-sm leading-relaxed text-foreground whitespace-pre-wrap font-sans">
          {fullText}
        </p>
      </div>
    );
  };

  return (
    <div
      className="fixed inset-0 z-50 flex justify-end bg-background/80 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      aria-labelledby="evidence-drawer-title"
    >
      <div className="relative w-full max-w-xl h-full bg-card border-l border-border flex flex-col shadow-2xl animate-in slide-in-from-right duration-200">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-border">
          <div className="flex items-center gap-2">
            <Bookmark className="h-5 w-5 text-primary" aria-hidden="true" />
            <h2 id="evidence-drawer-title" className="text-base font-semibold text-foreground">
              Evidence Viewer
            </h2>
            {citationLabel && (
              <Badge variant="outline" className="font-mono text-xs">
                {citationLabel}
              </Badge>
            )}
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-md text-muted-foreground hover:text-foreground hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            aria-label="Close evidence drawer"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {loading && (
            <div className="py-8 flex justify-center">
              <Spinner className="h-6 w-6" />
            </div>
          )}

          {error && !fullText && (
            <div className="p-3 text-xs text-destructive bg-destructive/10 border border-destructive/20 rounded">
              {error}
            </div>
          )}

          {/* Document Metadata Card */}
          <div className="rounded-lg border border-border bg-muted/40 p-4 space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
                Source Document
              </span>
              {docViewerUrl && (
                <a
                  href={docViewerUrl}
                  target="_blank"
                  rel="noreferrer"
                  className="text-xs text-primary hover:underline inline-flex items-center gap-1 font-medium"
                >
                  Inspect chunk in document <ExternalLink className="h-3 w-3" />
                </a>
              )}
            </div>
            <div className="font-medium text-foreground text-sm flex items-center gap-2">
              <FileText className="h-4 w-4 text-muted-foreground shrink-0" />
              <span>{docDetail?.title || "Document ID: " + (documentId ?? "Corpus Document")}</span>
            </div>
            {(docDetail?.organization || docDetail?.report_year) && (
              <div className="text-xs text-muted-foreground flex gap-3 pt-1">
                {docDetail.organization && <span>Institution: {docDetail.organization}</span>}
                {docDetail.report_year && <span>Year: {docDetail.report_year}</span>}
                {docDetail.document_type && <span>Type: {docDetail.document_type}</span>}
              </div>
            )}
          </div>

          {/* Location Provenance */}
          <div className="grid grid-cols-2 gap-3 text-xs">
            <div className="p-3 rounded-lg border border-border bg-card">
              <div className="text-muted-foreground flex items-center gap-1 mb-1">
                <Layers className="h-3.5 w-3.5" /> Section Provenance
              </div>
              <div className="font-semibold text-foreground truncate" title={resolvedSection}>
                {resolvedSection}
              </div>
            </div>
            <div className="p-3 rounded-lg border border-border bg-card">
              <div className="text-muted-foreground flex items-center gap-1 mb-1">
                <Bookmark className="h-3.5 w-3.5" /> Page Reference
              </div>
              <div className="font-semibold text-foreground">
                {resolvedPage !== null ? (
                  `Page ${resolvedPage}`
                ) : (
                  <span className="text-muted-foreground font-normal italic">
                    Section/anchor provenance (HTML source)
                  </span>
                )}
              </div>
            </div>
          </div>

          {/* Exact Evidence & Highlight */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-foreground flex items-center gap-1.5">
                <CheckCircle2 className="h-4 w-4 text-emerald-400" />
                Verified Textual Grounding
              </span>
              {chunkDetail?.chunk_type && (
                <Badge variant="secondary" className="text-[10px] uppercase">
                  {chunkDetail.chunk_type}
                </Badge>
              )}
            </div>
            <div className="rounded-lg border border-border bg-card p-4 space-y-3">
              {renderHighlightedContent()}

              {/* Informative notice for short section headers / TOC chunks */}
              {fullText.length > 0 && fullText.length < 80 && (
                <div className="p-3 rounded bg-primary/10 border border-primary/20 text-xs text-primary space-y-1">
                  <div className="font-semibold flex items-center gap-1.5">
                    <FileText className="h-3.5 w-3.5" /> Section Heading / Table of Contents Entry
                  </div>
                  <p className="text-foreground/90 leading-normal">
                    This evidence snippet is an indexed section heading. Click <strong>&quot;Open in Document Viewer&quot;</strong> to navigate directly to this position in the document and explore the surrounding content.
                  </p>
                </div>
              )}
            </div>
          </div>

          {/* Chunk Technical Metadata */}
          {chunkId && (
            <div className="pt-2 border-t border-border/60 text-xs text-muted-foreground space-y-1 font-mono">
              <div className="flex items-center gap-1">
                <Hash className="h-3 w-3" /> Chunk ID: {chunkId}
              </div>
              {chunkDetail?.chunk_index !== undefined && (
                <div>Sequence Index: #{chunkDetail.chunk_index}</div>
              )}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-3 border-t border-border flex items-center justify-between bg-card">
          {docViewerUrl ? (
            <a
              href={docViewerUrl}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center"
            >
              <Button size="sm" className="gap-1.5 text-xs">
                <ExternalLink className="h-3.5 w-3.5" /> Open in Document Viewer
              </Button>
            </a>
          ) : (
            <div />
          )}
          <Button variant="outline" size="sm" onClick={onClose}>
            Close
          </Button>
        </div>
      </div>
    </div>
  );
}
