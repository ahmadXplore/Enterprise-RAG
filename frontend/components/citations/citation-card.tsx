"use client";

import * as React from "react";
import { Bookmark, FileText } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { ChatCitationItem } from "@/lib/types";

export interface CitationCardProps {
  citation: ChatCitationItem;
  index: number;
  onSelect: (citation: ChatCitationItem) => void;
}

export function CitationCard({ citation, index, onSelect }: CitationCardProps) {
  const label = citation.citation_label ?? `[${index + 1}]`;

  return (
    <button
      type="button"
      onClick={() => onSelect(citation)}
      className="flex items-start gap-2.5 p-2.5 rounded-lg border border-border bg-card hover:bg-accent/40 text-left transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring group shadow-xs"
    >
      <Badge variant="outline" className="font-mono text-xs shrink-0 mt-0.5 group-hover:border-primary/60 font-semibold text-foreground">
        {label}
      </Badge>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-1.5 text-xs font-semibold text-foreground">
          <FileText className="h-3.5 w-3.5 text-primary shrink-0" />
          <span className="truncate">
            {citation.page !== null ? `Page ${citation.page}` : "Section Anchor"}
          </span>
        </div>
        {citation.evidence_text && (
          <p className="text-xs text-foreground/85 line-clamp-2 mt-1 italic font-serif">
            “{citation.evidence_text}”
          </p>
        )}
      </div>
      <Bookmark className="h-3.5 w-3.5 text-muted-foreground group-hover:text-primary shrink-0 mt-1" />
    </button>
  );
}
