"use client";

import * as React from "react";
import { Filter, RotateCcw } from "lucide-react";
import { Input } from "@/components/ui/input";

export interface SearchFilterState {
  company: string;
  year: string;
  documentType: string;
}

export interface FilterPanelProps {
  filters: SearchFilterState;
  onChange: (filters: SearchFilterState) => void;
  onReset: () => void;
}

export function FilterPanel({ filters, onChange, onReset }: FilterPanelProps) {
  const hasActiveFilters = Boolean(filters.company || filters.year || filters.documentType);

  return (
    <div className="rounded-lg border border-border bg-card p-4 space-y-3">
      <div className="flex items-center justify-between text-xs font-semibold text-muted-foreground uppercase tracking-wider">
        <div className="flex items-center gap-1.5">
          <Filter className="h-3.5 w-3.5 text-primary" />
          <span>Search Constraints</span>
        </div>
        {hasActiveFilters && (
          <button
            onClick={onReset}
            className="flex items-center gap-1 text-[11px] text-primary hover:underline lowercase font-normal"
          >
            <RotateCcw className="h-3 w-3" /> reset
          </button>
        )}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        <div>
          <Input
            list="company-filter-list"
            placeholder="Filter by institution (e.g. Harvard, UNESCO, OECD)..."
            value={filters.company}
            onChange={(e) => onChange({ ...filters, company: e.target.value })}
            className="h-8 text-xs"
          />
          <datalist id="company-filter-list">
            <option value="Harvard University" />
            <option value="MIT" />
            <option value="Stanford University" />
            <option value="OECD" />
            <option value="UNESCO" />
            <option value="World Bank" />
            <option value="Carnegie Mellon University" />
            <option value="UC Berkeley" />
            <option value="National Science Foundation" />
            <option value="Kaggle Academic Research" />
          </datalist>
        </div>

        <Input
          placeholder="Filter by year (e.g. 2024)..."
          type="number"
          value={filters.year}
          onChange={(e) => onChange({ ...filters, year: e.target.value })}
          className="h-8 text-xs"
        />

        <select
          value={filters.documentType}
          onChange={(e) => onChange({ ...filters, documentType: e.target.value })}
          aria-label="Filter search results by document type"
          className="h-8 rounded-md border border-input bg-card px-2.5 text-xs text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <option value="">All Document Types</option>
          <option value="research_paper">Research Paper / Study</option>
          <option value="dataset">Academic Dataset (CSV)</option>
          <option value="spreadsheet">Statistical Spreadsheet (XLSX)</option>
          <option value="syllabus">Course Syllabus / Curriculum</option>
          <option value="educational">Educational Report</option>
        </select>
      </div>
    </div>
  );
}
