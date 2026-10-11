"use client";

import * as React from "react";
import { Search as SearchIcon, Loader2, ArrowRight } from "lucide-react";
import { Button } from "@/components/ui/button";

export interface SearchInputProps {
  value: string;
  onChange: (val: string) => void;
  onSearch: () => void;
  loading?: boolean;
  placeholder?: string;
}

export function SearchInput({
  value,
  onChange,
  onSearch,
  loading = false,
  placeholder = "Search academic papers, educational datasets, literacy indicators, or syllabi...",
}: SearchInputProps) {
  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      e.preventDefault();
      onSearch();
    }
  };

  return (
    <div className="relative flex items-center w-full">
      <div className="absolute left-3 text-muted-foreground pointer-events-none">
        <SearchIcon className="h-4 w-4" />
      </div>
      <input
        type="search"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder={placeholder}
        aria-label="Corpus hybrid search input"
        className="w-full h-11 pl-10 pr-24 rounded-lg border border-input bg-card text-sm text-foreground placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring transition-shadow"
      />
      <div className="absolute right-1.5">
        <Button
          size="sm"
          onClick={onSearch}
          disabled={loading || !value.trim()}
          className="h-8 gap-1.5 text-xs px-3"
        >
          {loading ? (
            <>
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
              <span>Searching</span>
            </>
          ) : (
            <>
              <span>Search</span>
              <ArrowRight className="h-3.5 w-3.5" />
            </>
          )}
        </Button>
      </div>
    </div>
  );
}
