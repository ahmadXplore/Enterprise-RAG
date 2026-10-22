"use client";

import * as React from "react";
import Link from "next/link";
import {
  X,
  Upload,
  UploadCloud,
  FileText,
  FileSpreadsheet,
  CheckCircle2,
  AlertCircle,
  Loader2,
  ShieldCheck,
  Sparkles,
  ArrowRight,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { documentsApi } from "@/lib/api";

export interface UploadModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

export function UploadModal({ isOpen, onClose, onSuccess }: UploadModalProps) {
  const [file, setFile] = React.useState<File | null>(null);
  const [dragActive, setDragActive] = React.useState(false);
  const [title, setTitle] = React.useState("");
  const [org, setOrg] = React.useState("");
  const [year, setYear] = React.useState(new Date().getFullYear().toString());
  const [docType, setDocType] = React.useState("research_paper");

  const [submitting, setSubmitting] = React.useState(false);
  const [stage, setStage] = React.useState<string>("");
  const [error, setError] = React.useState<string | null>(null);
  const [successMessage, setSuccessMessage] = React.useState<string | null>(null);

  const fileInputRef = React.useRef<HTMLInputElement | null>(null);

  React.useEffect(() => {
    if (!isOpen) {
      setFile(null);
      setTitle("");
      setOrg("");
      setError(null);
      setSuccessMessage(null);
      setSubmitting(false);
      setStage("");
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFileSelected(e.dataTransfer.files[0]);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      handleFileSelected(e.target.files[0]);
    }
  };

  const handleFileSelected = (selectedFile: File) => {
    setFile(selectedFile);
    setError(null);
    if (!title) {
      const cleanName = selectedFile.name
        .replace(/\.[^/.]+$/, "")
        .replace(/[_-]/g, " ");
      setTitle(cleanName);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) {
      setError("Please select a document file (.pdf, .docx, .csv, .xlsx).");
      return;
    }
    if (!title.trim()) {
      setError("Document title is required.");
      return;
    }

    setSubmitting(true);
    setError(null);
    setSuccessMessage(null);
    setStage("Scanning file integrity & malicious payload defense...");

    try {
      const formData = new FormData();
      formData.append("file", file);
      formData.append("title", title.trim());
      if (org.trim()) formData.append("organization", org.trim());
      if (year.trim()) formData.append("report_year", year.trim());
      if (docType) formData.append("document_type", docType);

      setStage("Uploading document & enqueuing pipeline...");
      const res = await documentsApi.upload(formData);

      setSuccessMessage(res.message || `Successfully uploaded "${title}". Ingestion pipeline started.`);
      onSuccess();
      // Reset inputs
      setFile(null);
      setTitle("");
      setOrg("");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to upload document");
    } finally {
      setSubmitting(false);
      setStage("");
    }
  };

  const isSpreadsheet = file?.name.endsWith(".csv") || file?.name.endsWith(".xlsx");

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs p-4 animate-in fade-in duration-200"
      role="dialog"
      aria-modal="true"
    >
      <div className="w-full max-w-lg rounded-2xl border border-border bg-card shadow-2xl p-6 space-y-4 max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-border pb-3">
          <div className="flex items-center gap-2.5">
            <div className="h-8 w-8 rounded-lg bg-primary/10 border border-primary/20 flex items-center justify-center text-primary">
              <Upload className="h-4 w-4" />
            </div>
            <div>
              <h2 className="text-base font-bold text-foreground">Upload & Ingest Document</h2>
              <p className="text-xs text-muted-foreground">
                Indexed directly into the Qdrant vector database
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            disabled={submitting}
            className="p-1.5 rounded-lg text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Security Scanner Status Badge */}
        <div className="flex items-center gap-2 p-2.5 rounded-lg bg-emerald-50 dark:bg-emerald-950/30 border border-emerald-500/30 text-emerald-800 dark:text-emerald-300 text-xs">
          <ShieldCheck className="h-4 w-4 text-emerald-600 dark:text-emerald-400 shrink-0" />
          <span className="leading-tight">
            <strong>Active Security Scanner:</strong> Validates file magic bytes, blocks embedded PDF scripts/launch exploits, scans Office archives for VBA macros, and sanitizes CSV formula injection.
          </span>
        </div>

        {error && (
          <div className="flex items-start gap-2 p-3 rounded-lg bg-destructive/10 border border-destructive/20 text-xs text-destructive">
            <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
            <span>{error}</span>
          </div>
        )}

        {successMessage && (
          <div className="p-3 rounded-lg bg-emerald-50 dark:bg-emerald-950/30 border border-emerald-500/30 text-xs text-emerald-800 dark:text-emerald-300 space-y-2">
            <div className="flex items-center gap-2 font-medium">
              <CheckCircle2 className="h-4 w-4 text-emerald-600 shrink-0" />
              <span>{successMessage}</span>
            </div>
            <div className="flex items-center justify-between pt-1 border-t border-emerald-500/20">
              <span className="text-[11px] text-muted-foreground">
                You can freely navigate away while processing continues.
              </span>
              <div className="flex items-center gap-2">
                <Link
                  href="/admin/jobs"
                  className="inline-flex items-center gap-1 font-semibold text-primary hover:underline"
                  onClick={onClose}
                >
                  Jobs Monitor <ArrowRight className="h-3 w-3" />
                </Link>
                <button
                  type="button"
                  onClick={onClose}
                  className="px-2 py-0.5 rounded bg-emerald-600 text-white font-medium hover:bg-emerald-700 text-[11px]"
                >
                  Done
                </button>
              </div>
            </div>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Drag & Drop File Zone */}
          <div
            onDragEnter={handleDrag}
            onDragLeave={handleDrag}
            onDragOver={handleDrag}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
            className={`border-2 border-dashed rounded-xl p-5 text-center cursor-pointer transition-all ${
              dragActive
                ? "border-primary bg-primary/10"
                : file
                ? "border-emerald-500/50 bg-emerald-500/5"
                : "border-border hover:border-primary/50 hover:bg-muted/30"
            }`}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf,.docx,.csv,.xlsx,.txt"
              onChange={handleFileChange}
              className="hidden"
            />
            {file ? (
              <div className="flex items-center justify-between gap-3 text-left p-2 rounded-lg bg-card border border-border shadow-xs">
                <div className="flex items-center gap-2.5 min-w-0">
                  {isSpreadsheet ? (
                    <FileSpreadsheet className="h-6 w-6 text-emerald-600 shrink-0" />
                  ) : (
                    <FileText className="h-6 w-6 text-primary shrink-0" />
                  )}
                  <div className="min-w-0">
                    <div className="font-semibold text-xs text-foreground truncate">{file.name}</div>
                    <div className="text-[11px] text-muted-foreground font-mono">
                      {(file.size / 1024).toFixed(1)} KB • {file.name.split(".").pop()?.toUpperCase()}
                    </div>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    setFile(null);
                  }}
                  className="p-1 rounded text-muted-foreground hover:text-destructive hover:bg-destructive/10"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>
            ) : (
              <div className="space-y-2 py-2">
                <div className="h-10 w-10 mx-auto rounded-full bg-primary/10 flex items-center justify-center text-primary">
                  <UploadCloud className="h-5 w-5" />
                </div>
                <div className="text-xs font-semibold text-foreground">
                  Click to browse or drag & drop document
                </div>
                <p className="text-[11px] text-muted-foreground">
                  Supported formats: PDF, DOCX, CSV, XLSX, TXT (Max 50MB)
                </p>
              </div>
            )}
          </div>

          {/* Metadata Inputs */}
          <div className="space-y-3">
            <Input
              label="Document Title *"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g. OECD Education at a Glance Report 2024"
              required
              disabled={submitting}
            />

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <Input
                label="Institution / Organization"
                value={org}
                onChange={(e) => setOrg(e.target.value)}
                placeholder="e.g. Stanford University / OECD"
                disabled={submitting}
              />
              <Input
                label="Publication Year"
                type="number"
                value={year}
                onChange={(e) => setYear(e.target.value)}
                min="1900"
                max="2100"
                disabled={submitting}
              />
            </div>

            <div className="space-y-1">
              <label className="text-xs font-medium text-foreground">Document Type</label>
              <select
                value={docType}
                onChange={(e) => setDocType(e.target.value)}
                disabled={submitting}
                className="w-full h-9 rounded-md border border-input bg-card px-3 text-xs text-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
              >
                <option value="research_paper">Academic Research Paper</option>
                <option value="syllabus">Course Syllabus / Curriculum</option>
                <option value="dataset">Statistical Education Dataset</option>
                <option value="spreadsheet">Spreadsheet / Metric Table</option>
                <option value="policy_report">Policy & Benchmarking Report</option>
              </select>
            </div>
          </div>

          {/* Ingestion Status Feed */}
          {submitting && (
            <div className="p-3 rounded-lg border border-primary/20 bg-primary/5 flex items-center gap-2.5 text-xs text-primary font-medium">
              <Loader2 className="h-4 w-4 animate-spin shrink-0" />
              <span>{stage}</span>
            </div>
          )}

          {/* Actions */}
          <div className="flex items-center justify-end gap-2 pt-2 border-t border-border">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={onClose}
              disabled={submitting}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              size="sm"
              disabled={submitting || !file || !title.trim()}
              className="gap-1.5 shadow-sm"
            >
              {submitting ? (
                <>
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  <span>Ingesting...</span>
                </>
              ) : (
                <>
                  <Sparkles className="h-3.5 w-3.5" />
                  <span>Upload & Ingest</span>
                </>
              )}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
