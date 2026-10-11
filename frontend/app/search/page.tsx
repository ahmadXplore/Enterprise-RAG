"use client";

import * as React from "react";
import { Database, Sparkles, Info, BookOpen, ArrowRight } from "lucide-react";
import { AppShell } from "@/components/layout/app-shell";
import { SearchInput } from "@/components/search/search-input";
import { FilterPanel, SearchFilterState } from "@/components/search/filter-panel";
import { ResultCard } from "@/components/search/result-card";
import { EvidenceDrawer } from "@/components/citations/evidence-drawer";
import { Spinner, EmptyState, ErrorState } from "@/components/ui/states";
import { searchApi } from "@/lib/api";
import { SearchResultItem } from "@/lib/types";

export default function SearchPage() {
  const [query, setQuery] = React.useState("");
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [results, setResults] = React.useState<SearchResultItem[]>([]);
  const [serverMessage, setServerMessage] = React.useState<string | null>(null);
  const [availableResources, setAvailableResources] = React.useState<string[]>([]);
  const [hasSearched, setHasSearched] = React.useState(false);

  const [filters, setFilters] = React.useState<SearchFilterState>({
    company: "",
    year: "",
    documentType: "",
  });

  // Drawer state for Phase 15 evidence viewing
  const [activeItem, setActiveItem] = React.useState<SearchResultItem | null>(null);
  const [isDrawerOpen, setIsDrawerOpen] = React.useState(false);

  const handleSearch = async () => {
    if (!query.trim()) return;
    setLoading(true);
    setError(null);
    setServerMessage(null);
    setAvailableResources([]);
    setHasSearched(true);

    try {
      const res = await searchApi.search({
        query: query.trim(),
        top_k: 15,
        filters: {
          companies: filters.company ? [filters.company] : undefined,
          years: filters.year ? [parseInt(filters.year, 10)] : undefined,
          document_type: filters.documentType || undefined,
        },
      });
      setResults(res.results || []);
      setServerMessage(res.message || null);
      setAvailableResources(res.available_resources || []);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Search request failed");
      setResults([]);
    } finally {
      setLoading(false);
    }
  };

  const handleViewEvidence = (item: SearchResultItem) => {
    setActiveItem(item);
    setIsDrawerOpen(true);
  };

  return (
    <AppShell>
      <div className="p-6 max-w-5xl mx-auto space-y-6">
        {/* Header */}
        <div className="space-y-1">
          <h1 className="text-xl font-bold tracking-tight text-foreground flex items-center gap-2">
            <Database className="h-5 w-5 text-primary" />
            Corpus Hybrid Search
          </h1>
          <p className="text-xs text-muted-foreground">
            Dense semantic vectors + BM25 keyword matching with cross-encoder reranking
          </p>
        </div>

        {/* Search Input Bar */}
        <SearchInput
          value={query}
          onChange={setQuery}
          onSearch={handleSearch}
          loading={loading}
        />

        {/* Filter Constraints Panel */}
        <FilterPanel
          filters={filters}
          onChange={setFilters}
          onReset={() => setFilters({ company: "", year: "", documentType: "" })}
        />

        {/* Results Stream */}
        <div className="space-y-4">
          {loading ? (
            <div className="py-20 flex flex-col items-center justify-center gap-3">
              <Spinner className="h-8 w-8" />
              <span className="text-xs text-muted-foreground">
                Executing dense + sparse retrieval and reciprocal rank fusion...
              </span>
            </div>
          ) : error ? (
            <ErrorState message={error} onRetry={handleSearch} />
          ) : hasSearched && results.length === 0 ? (
            serverMessage ? (
              <div className="rounded-xl border border-primary/20 bg-card p-6 shadow-sm space-y-4">
                <div className="flex items-start gap-3">
                  <div className="p-2 rounded-lg bg-primary/10 text-primary mt-0.5">
                    <Info className="h-5 w-5" />
                  </div>
                  <div className="space-y-1">
                    <h3 className="text-sm font-semibold text-foreground">
                      Repository Availability Notice
                    </h3>
                    <p className="text-xs text-muted-foreground leading-relaxed">
                      {serverMessage}
                    </p>
                  </div>
                </div>

                {availableResources && availableResources.length > 0 && (
                  <div className="pt-3 border-t border-border/80 space-y-2">
                    <div className="text-xs font-medium text-foreground flex items-center gap-1.5">
                      <BookOpen className="h-3.5 w-3.5 text-primary" />
                      <span>Available documents for this institution:</span>
                    </div>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                      {availableResources.map((resTitle) => (
                        <button
                          key={resTitle}
                          type="button"
                          onClick={() => {
                            setQuery(resTitle);
                            // Keep institution filter and search
                            setTimeout(() => {
                              handleSearch();
                            }, 50);
                          }}
                          className="flex items-center justify-between p-2.5 rounded-lg border border-border bg-card hover:bg-accent/40 text-left text-xs text-foreground/90 font-medium hover:text-foreground transition-colors group shadow-sm"
                        >
                          <span className="truncate pr-2">{resTitle}</span>
                          <ArrowRight className="h-3.5 w-3.5 text-muted-foreground group-hover:text-primary shrink-0 transition-transform group-hover:translate-x-0.5" />
                        </button>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <EmptyState
                title="No documents found in database"
                description="No matching passages were found for your query and filter combination. Try adjusting or clearing search constraints."
              />
            )
          ) : (
            results.length > 0 && (
              <div className="space-y-4">
                <div className="text-xs text-muted-foreground flex items-center justify-between border-b border-border pb-2">
                  <span>Found {results.length} ranked candidate chunks</span>
                  <span className="font-mono text-[11px] text-primary flex items-center gap-1">
                    <Sparkles className="h-3 w-3" /> Cross-encoder reranked
                  </span>
                </div>

                <div className="space-y-3">
                  {results.map((item) => (
                    <ResultCard
                      key={item.chunk_id}
                      item={item}
                      onViewEvidence={handleViewEvidence}
                    />
                  ))}
                </div>
              </div>
            )
          )}
        </div>

        {/* Phase 15 Evidence Drawer */}
        <EvidenceDrawer
          isOpen={isDrawerOpen}
          onClose={() => setIsDrawerOpen(false)}
          chunkId={activeItem?.chunk_id ?? null}
          documentId={activeItem?.document_id}
          evidenceText={activeItem?.text}
          page={activeItem?.page}
        />
      </div>
    </AppShell>
  );
}
