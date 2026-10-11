"use client";

import * as React from "react";
import Link from "next/link";
import { FileText, Bookmark, ExternalLink } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { SearchResultItem } from "@/lib/types";

export interface ResultCardProps {
  item: SearchResultItem;
  onViewEvidence: (item: SearchResultItem) => void;
}

export function ResultCard({ item, onViewEvidence }: ResultCardProps) {
  // Calibrate score to safe 0 - 100% confidence percentage via sigmoid if unbounded
  const normalizedProb =
    item.score >= 0 && item.score <= 1
      ? item.score
      : 1 / (1 + Math.exp(-item.score));
  const scorePercent = Math.min(100, Math.max(0, Math.round(normalizedProb * 100)));

  return (
    <div className="rounded-lg border border-border bg-card p-5 space-y-3 hover:border-primary/50 transition-colors">
      <div className="flex items-start justify-between gap-4">
        <div className="space-y-1.5">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="text-sm font-semibold text-foreground flex items-center gap-1.5">
              <FileText className="h-4 w-4 text-primary shrink-0" />
              <span>{item.document_title || item.company || "Academic Document"}</span>
            </h3>
            {item.document_type && (
              <Badge variant="secondary" className="text-[10px] uppercase font-mono tracking-wider py-0 px-1.5 bg-primary/10 text-primary border-primary/20">
                {item.document_type.replace("_", " ")}
              </Badge>
            )}
          </div>
          <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
            {item.company && (
              <span className="font-semibold text-foreground/90">{item.company}</span>
            )}
            {item.year && <span>• {item.year}</span>}
            {item.page !== null && (
              <>
                <span className="text-border">•</span>
                <span className="flex items-center gap-1 font-mono">
                  <Bookmark className="h-3 w-3" /> Page {item.page}
                </span>
              </>
            )}
            <span className="text-border">•</span>
            <span className="font-mono text-[11px] text-muted-foreground">
              Chunk: {item.chunk_id.slice(0, 8)}...
            </span>
          </div>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          <Badge
            variant="outline"
            className={`text-xs font-mono ${
              scorePercent >= 70
                ? "text-emerald-700 dark:text-emerald-400 border-emerald-500/40"
                : scorePercent >= 40
                ? "text-sky-700 dark:text-sky-400 border-sky-500/40"
                : "text-muted-foreground border-border"
            }`}
          >
            Score: {normalizedProb.toFixed(3)}
          </Badge>
        </div>
      </div>

      <div className="p-3 rounded-md bg-muted/40 border border-border/70">
        <p className="text-xs text-foreground leading-relaxed font-sans line-clamp-3">
          {item.text}
        </p>
      </div>

      <div className="flex items-center justify-between pt-1">
        <div className="text-[11px] text-muted-foreground flex items-center gap-2">
          <span>Relevance: {scorePercent}%</span>
          <div className="w-16 h-1.5 bg-muted rounded-full overflow-hidden">
            <div
              className={`h-full rounded-full ${
                scorePercent >= 70
                  ? "bg-emerald-500"
                  : scorePercent >= 40
                  ? "bg-sky-500"
                  : "bg-amber-500"
              }`}
              style={{ width: `${scorePercent}%` }}
            />
          </div>
        </div>
        <div className="flex items-center gap-2">
          {item.document_id && (
            <Link href={`/documents/${item.document_id}?chunk=${item.chunk_id}`} target="_blank">
              <Button variant="ghost" size="sm" className="h-7 text-xs px-2.5 gap-1 hover:text-primary hover:bg-primary/10">
                <ExternalLink className="h-3 w-3" />
                <span>Open Document</span>
              </Button>
            </Link>
          )}
          <Button
            variant="outline"
            size="sm"
            onClick={() => onViewEvidence(item)}
            className="h-7 text-xs px-2.5 gap-1 text-primary hover:text-primary hover:bg-primary/10"
          >
            <Bookmark className="h-3 w-3" />
            <span>View Evidence</span>
          </Button>
        </div>
      </div>
    </div>
  );
}
