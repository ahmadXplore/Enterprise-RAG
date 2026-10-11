"use client";

import * as React from "react";
import { ChevronRight, ChevronDown, Folder, FileText, Bookmark } from "lucide-react";
import { DocumentSectionRead } from "@/lib/types";

export interface SectionTreeProps {
  sections: DocumentSectionRead[];
  selectedSectionId?: string | null;
  onSelectSection?: (section: DocumentSectionRead) => void;
}

export function SectionTree({ sections, selectedSectionId, onSelectSection }: SectionTreeProps) {
  const [expandedIds, setExpandedIds] = React.useState<Set<string>>(new Set());

  // Expand all by default if small tree
  React.useEffect(() => {
    if (sections.length < 25) {
      setExpandedIds(new Set(sections.map((s) => s.id)));
    }
  }, [sections]);

  const toggleExpand = (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setExpandedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  if (sections.length === 0) {
    return (
      <div className="p-4 text-xs text-muted-foreground italic text-center">
        No document section hierarchy indexed.
      </div>
    );
  }

  return (
    <div className="space-y-1 py-1 font-mono text-xs">
      {sections.map((sec) => {
        const isSelected = selectedSectionId === sec.id;
        const level = sec.heading_level ?? 1;
        const indentClass =
          level === 1 ? "pl-2" : level === 2 ? "pl-5" : level === 3 ? "pl-8" : "pl-11";

        return (
          <div
            key={sec.id}
            onClick={() => onSelectSection?.(sec)}
            className={`flex items-center justify-between py-1.5 px-2 rounded cursor-pointer transition-colors ${indentClass} ${
              isSelected ? "bg-primary/20 text-primary font-medium" : "hover:bg-accent/40 text-foreground/80 hover:text-foreground"
            }`}
          >
            <div className="flex items-center gap-2 truncate">
              {level <= 2 ? (
                <Folder className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
              ) : (
                <FileText className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
              )}
              <span className="truncate">{sec.heading || "Untitled Section"}</span>
            </div>

            {sec.page_start !== null && (
              <span className="text-[10px] text-muted-foreground shrink-0 ml-2">
                p.{sec.page_start}
                {sec.page_end && sec.page_end !== sec.page_start ? `–${sec.page_end}` : ""}
              </span>
            )}
          </div>
        );
      })}
    </div>
  );
}
