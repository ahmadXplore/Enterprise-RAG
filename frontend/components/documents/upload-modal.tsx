"use client";

import * as React from "react";
import { X, Upload, CheckCircle2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export interface UploadModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

export function UploadModal({ isOpen, onClose, onSuccess }: UploadModalProps) {
  const [title, setTitle] = React.useState("");
  const [org, setOrg] = React.useState("");
  const [year, setYear] = React.useState(new Date().getFullYear().toString());
  const [docType, setDocType] = React.useState("research_paper");
  const [submitting, setSubmitting] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim()) {
      setError("Title is required");
      return;
    }

    setSubmitting(true);
    setError(null);

    try {
      // Mock hash generation for registration
      const contentHash = Array.from(crypto.getRandomValues(new Uint8Array(32)))
        .map((b) => b.toString(16).padStart(2, "0"))
        .join("");

      const res = await fetch("http://localhost:8000/api/v1/documents", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${localStorage.getItem("rag_access_token") ?? ""}`,
        },
        body: JSON.stringify({
          title,
          organization: org || null,
          report_year: parseInt(year, 10) || null,
          document_type: docType,
          source_type: "educational",
          content_hash: contentHash,
          language: "en",
        }),
      });

      if (!res.ok) {
        const data = await res.json().catch(() => null);
        throw new Error(data?.detail || "Failed to register document");
      }

      onSuccess();
      onClose();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Error creating document");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-background/80 backdrop-blur-sm p-4"
      role="dialog"
      aria-modal="true"
    >
      <div className="w-full max-w-md rounded-lg border border-border bg-card shadow-2xl p-6 space-y-4">
        <div className="flex items-center justify-between border-b border-border pb-3">
          <div className="flex items-center gap-2">
            <Upload className="h-5 w-5 text-primary" />
            <h2 className="text-base font-semibold text-foreground">Register New Document</h2>
          </div>
          <button onClick={onClose} className="p-1 rounded-md text-muted-foreground hover:text-foreground">
            <X className="h-4 w-4" />
          </button>
        </div>

        {error && (
          <div className="p-2.5 rounded bg-destructive/10 border border-destructive/20 text-xs text-destructive">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-3">
          <Input
            label="Document Title *"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="e.g. OECD Education at a Glance Report 2024"
            required
          />

          <div className="grid grid-cols-2 gap-3">
            <Input
              label="Institution / Organization"
              value={org}
              onChange={(e) => setOrg(e.target.value)}
              placeholder="e.g. UNESCO, OECD, Harvard"
            />
            <Input
              label="Report Year"
              type="number"
              value={year}
              onChange={(e) => setYear(e.target.value)}
              placeholder="2025"
            />
          </div>

          <div>
            <label className="text-xs font-medium text-foreground block mb-1">Document Type</label>
            <select
              value={docType}
              onChange={(e) => setDocType(e.target.value)}
              className="w-full h-9 rounded-md border border-input bg-card px-3 text-xs text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              <option value="research_paper">Research Paper / Study</option>
              <option value="dataset">Academic Dataset (CSV)</option>
              <option value="spreadsheet">Statistical Spreadsheet (XLSX)</option>
              <option value="syllabus">Course Syllabus / Curriculum</option>
              <option value="educational">Educational Policy / Report</option>
            </select>
          </div>

          <div className="pt-2 flex justify-end gap-2 border-t border-border">
            <Button type="button" variant="outline" size="sm" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit" size="sm" disabled={submitting}>
              {submitting ? "Registering..." : "Register Document"}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
