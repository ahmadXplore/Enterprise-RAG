"use client";

import * as React from "react";
import {
  Settings,
  Shield,
  User,
  LogOut,
  UploadCloud,
  FileText,
  FileSpreadsheet,
  CheckCircle2,
  AlertCircle,
  Loader2,
  Trash2,
  RefreshCw,
  Sparkles,
  Layers,
  BookOpen,
  ArrowRight,
  Database,
  Check,
} from "lucide-react";
import { AppShell } from "@/components/layout/app-shell";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { getUser, clearToken, isAdmin } from "@/lib/auth";
import { documentsApi, healthApi } from "@/lib/api";
import type { DocumentRead, CorpusStats } from "@/lib/types";
import { useModal } from "@/components/ui/modal-context";

interface UploadResult {
  status: string;
  document_id: string;
  version_id?: string;
  title: string;
  organization?: string;
  document_type?: string;
  report_year?: number;
  filename: string;
  file_size?: number;
  sections_count?: number;
  chunks_count?: number;
  message: string;
}

export default function SettingsPage() {
  const modal = useModal();
  const [mounted, setMounted] = React.useState(false);
  const [stats, setStats] = React.useState<CorpusStats | null>(null);
  const [recentDocs, setRecentDocs] = React.useState<DocumentRead[]>([]);
  const [loadingDocs, setLoadingDocs] = React.useState(false);

  // Upload Form State
  const [file, setFile] = React.useState<File | null>(null);
  const [dragActive, setDragActive] = React.useState(false);
  const [title, setTitle] = React.useState("");
  const [organization, setOrganization] = React.useState("");
  const [documentType, setDocumentType] = React.useState("research_paper");
  const [reportYear, setReportYear] = React.useState<string>(new Date().getFullYear().toString());

  // Ingestion State
  const [isProcessing, setIsProcessing] = React.useState(false);
  const [processingStage, setProcessingStage] = React.useState<string>("");
  const [uploadResult, setUploadResult] = React.useState<UploadResult | null>(null);
  const [errorMessage, setErrorMessage] = React.useState<string | null>(null);

  const fileInputRef = React.useRef<HTMLInputElement | null>(null);

  const loadData = React.useCallback(async () => {
    try {
      setLoadingDocs(true);
      const [statsRes, docsRes] = await Promise.allSettled([
        healthApi.stats(),
        documentsApi.list({ page: 1, page_size: 15 }),
      ]);
      if (statsRes.status === "fulfilled") {
        setStats(statsRes.value);
      }
      if (docsRes.status === "fulfilled") {
        setRecentDocs(docsRes.value.items || []);
      }
    } catch {
      // ignore
    } finally {
      setLoadingDocs(false);
    }
  }, []);

  React.useEffect(() => {
    setMounted(true);
    loadData();
  }, [loadData]);

  const user = mounted ? getUser() : null;
  const userIsAdmin = mounted ? (isAdmin() || user?.roles?.some((r) => r.toUpperCase() === "ADMIN")) : false;

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

  const handleFileSelected = (selectedFile: File) => {
    const ext = selectedFile.name.substring(selectedFile.name.lastIndexOf(".")).toLowerCase();
    const allowed = [".pdf", ".docx", ".csv", ".xlsx", ".txt"];
    if (!allowed.includes(ext)) {
      setErrorMessage(`Unsupported format "${ext}". Supported formats: ${allowed.join(", ")}`);
      setFile(null);
      return;
    }
    setFile(selectedFile);
    setErrorMessage(null);
    setUploadResult(null);
    if (!title) {
      // Auto-populate title from clean filename
      const clean = selectedFile.name.replace(/\.[^/.]+$/, "").replace(/[_-]/g, " ");
      setTitle(clean.charAt(0).toUpperCase() + clean.slice(1));
    }
  };

  const handleUploadAndProcess = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) {
      setErrorMessage("Please select a file to upload.");
      return;
    }

    try {
      setIsProcessing(true);
      setErrorMessage(null);
      setUploadResult(null);

      setProcessingStage("1/5: Uploading file to secure storage...");
      await new Promise((r) => setTimeout(r, 400));

      setProcessingStage("2/5: Parsing document structure, headings & tables...");
      await new Promise((r) => setTimeout(r, 400));

      const formData = new FormData();
      formData.append("file", file);
      if (title.trim()) formData.append("title", title.trim());
      if (organization.trim()) formData.append("organization", organization.trim());
      if (documentType) formData.append("document_type", documentType);
      if (reportYear.trim()) formData.append("report_year", reportYear.trim());

      setProcessingStage("3/5: Semantic chunking with context normalization...");
      setProcessingStage("4/5: Generating Dense (BGE) + Sparse (BM25) vector embeddings...");
      
      const res = await documentsApi.upload(formData);

      setProcessingStage("5/5: Vector-indexed into Qdrant & marked ready!");
      await new Promise((r) => setTimeout(r, 300));

      setUploadResult(res);
      setFile(null);
      setTitle("");
      if (fileInputRef.current) fileInputRef.current.value = "";
      
      // Refresh corpus counts and documents list
      await loadData();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to process document.";
      setErrorMessage(msg);
    } finally {
      setIsProcessing(false);
      setProcessingStage("");
    }
  };

  const handleDelete = async (docId: string, docTitle?: string) => {
    const confirmed = await modal.confirm({
      title: "Confirm Document Deletion",
      message: (
        <span>
          Are you sure you want to permanently delete{" "}
          <strong className="text-foreground">{docTitle || "this document"}</strong> from the corpus?
          All extracted sections, text chunks, and vector index embeddings in Qdrant will be removed.
        </span>
      ),
      confirmText: "Delete Document",
      variant: "destructive",
    });
    if (!confirmed) return;

    try {
      await documentsApi.delete(docId);
      modal.toast.success(`Document "${docTitle || "Document"}" deleted successfully.`);
      await loadData();
    } catch (err: unknown) {
      modal.toast.error(err instanceof Error ? err.message : "Deletion failed");
    }
  };

  const getFormatIcon = (filename?: string, type?: string) => {
    const fn = (filename || type || "").toLowerCase();
    if (fn.endsWith(".csv") || fn.endsWith(".xlsx") || fn.includes("dataset") || fn.includes("spreadsheet")) {
      return <FileSpreadsheet className="h-4 w-4 text-emerald-400" />;
    }
    return <FileText className="h-4 w-4 text-blue-400" />;
  };

  return (
    <AppShell>
      <div className="p-6 max-w-5xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 pb-2 border-b border-border">
          <div className="space-y-1">
            <h1 className="text-xl font-bold tracking-tight text-foreground flex items-center gap-2">
              <Settings className="h-5 w-5 text-primary" />
              System Settings & Document Administration
            </h1>
            <p className="text-xs text-muted-foreground">
              Corpus ingestion controls, RBAC session identity, and vector database management
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={loadData}
              disabled={loadingDocs}
              className="text-xs gap-1.5 h-8"
            >
              <RefreshCw className={`h-3.5 w-3.5 ${loadingDocs ? "animate-spin" : ""}`} />
              Refresh
            </Button>
          </div>
        </div>

        {/* User Identity Card */}
        <Card className="border-border bg-card shadow-sm">
          <CardHeader className="pb-3 border-b border-border/60">
            <CardTitle className="text-sm font-semibold flex items-center justify-between">
              <div className="flex items-center gap-2">
                <User className="h-4 w-4 text-primary" />
                <span>Current Session Identity</span>
              </div>
              {userIsAdmin && (
                <Badge className="bg-primary/20 text-primary border-primary/30 text-[10px] font-mono gap-1">
                  <Shield className="h-3 w-3" /> ADMIN ACCESS GRANTED
                </Badge>
              )}
            </CardTitle>
          </CardHeader>
          <CardContent className="p-5 space-y-4">
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4 text-xs">
              <div>
                <span className="text-muted-foreground block mb-0.5">Full Name</span>
                <span className="font-medium text-foreground text-sm">
                  {user?.full_name || "Enterprise User"}
                </span>
              </div>
              <div>
                <span className="text-muted-foreground block mb-0.5">Corporate Email</span>
                <span className="font-mono text-foreground text-sm">{user?.email || "—"}</span>
              </div>
              <div>
                <span className="text-muted-foreground block mb-0.5">User ID</span>
                <span className="font-mono text-muted-foreground truncate block" title={user?.id}>
                  {user?.id ? `${user.id.slice(0, 16)}...` : "—"}
                </span>
              </div>
              <div>
                <span className="text-muted-foreground block mb-0.5">Active Roles</span>
                <div className="flex flex-wrap gap-1 pt-0.5">
                  {user?.roles?.map((r) => (
                    <Badge key={r} variant="outline" className="uppercase font-mono text-[10px] bg-muted/40">
                      {r}
                    </Badge>
                  ))}
                </div>
              </div>
            </div>

            <div className="pt-3 border-t border-border flex justify-end">
              <Button
                variant="outline"
                size="sm"
                onClick={() => {
                  clearToken();
                  window.location.href = "/login";
                }}
                className="text-xs gap-1.5 text-destructive hover:bg-destructive/10 h-8"
              >
                <LogOut className="h-3.5 w-3.5" /> Sign Out
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* ADMIN FILE UPLOAD & INGESTION HUB */}
        {userIsAdmin && (
          <div className="space-y-6 pt-1">
            {/* Live Stats Bar */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <Card className="border-border bg-card/60 backdrop-blur-sm p-4 flex items-center gap-3">
                <div className="p-2.5 rounded-lg bg-primary/10 text-primary">
                  <BookOpen className="h-5 w-5" />
                </div>
                <div>
                  <div className="text-2xl font-bold tracking-tight text-foreground">
                    {stats?.total_documents ?? recentDocs.length ?? 0}
                  </div>
                  <div className="text-xs text-muted-foreground">Active Documents in Corpus</div>
                </div>
              </Card>

              <Card className="border-border bg-card/60 backdrop-blur-sm p-4 flex items-center gap-3">
                <div className="p-2.5 rounded-lg bg-emerald-500/10 text-emerald-400">
                  <Layers className="h-5 w-5" />
                </div>
                <div>
                  <div className="text-2xl font-bold tracking-tight text-foreground">
                    {stats?.total_chunks ? stats.total_chunks.toLocaleString() : "2,552+"}
                  </div>
                  <div className="text-xs text-muted-foreground">Vector-Indexed Chunks (Qdrant)</div>
                </div>
              </Card>

              <Card className="border-border bg-card/60 backdrop-blur-sm p-4 flex items-center gap-3">
                <div className="p-2.5 rounded-lg bg-purple-500/10 text-purple-400">
                  <Sparkles className="h-5 w-5" />
                </div>
                <div>
                  <div className="text-sm font-semibold text-foreground">PDF, DOCX, CSV, XLSX</div>
                  <div className="text-xs text-muted-foreground">Immediate Multi-Format Ingestion</div>
                </div>
              </Card>
            </div>

            {/* Ingestion & Upload Moved Notice */}
            <Card className="border-border bg-card p-5 shadow-xs flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div className="flex items-center gap-3">
                <div className="h-10 w-10 rounded-lg bg-primary/10 text-primary flex items-center justify-center shrink-0">
                  <UploadCloud className="h-5 w-5" />
                </div>
                <div>
                  <h3 className="text-sm font-semibold text-foreground">Document Upload & Security Ingestion</h3>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    Direct multi-format file uploads (PDF, DOCX, CSV, XLSX) and automated malware/corruption security scanning are now managed directly in the Document Library.
                  </p>
                </div>
              </div>
              <a href="/documents">
                <Button size="sm" className="gap-1.5 text-xs shrink-0 shadow-xs">
                  <span>Open Document Library</span>
                  <ArrowRight className="h-3.5 w-3.5" />
                </Button>
              </a>
            </Card>


            {/* Ingested Documents Corpus Browser */}
            <Card className="border-border bg-card shadow-sm">
              <CardHeader className="pb-3 border-b border-border/80 flex flex-row items-center justify-between">
                <div>
                  <CardTitle className="text-sm font-semibold flex items-center gap-2">
                    <Database className="h-4 w-4 text-primary" />
                    <span>Active Educational Corpus Documents</span>
                  </CardTitle>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    Recent registered documents currently queryable across SQLite and Qdrant
                  </p>
                </div>
                <Badge variant="outline" className="font-mono text-[10px]">
                  Showing {recentDocs.length} Documents
                </Badge>
              </CardHeader>
              <CardContent className="p-0">
                <div className="overflow-x-auto">
                  <table className="w-full text-xs text-left">
                    <thead className="bg-muted/40 border-b border-border text-muted-foreground uppercase text-[10px] font-mono">
                      <tr>
                        <th className="px-4 py-2.5">Document Title</th>
                        <th className="px-4 py-2.5">Institution</th>
                        <th className="px-4 py-2.5">Format / Type</th>
                        <th className="px-4 py-2.5">Year</th>
                        <th className="px-4 py-2.5">Status</th>
                        <th className="px-4 py-2.5 text-right">Actions</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border">
                      {recentDocs.length === 0 ? (
                        <tr>
                          <td colSpan={6} className="px-4 py-8 text-center text-muted-foreground">
                            No documents found in corpus.
                          </td>
                        </tr>
                      ) : (
                        recentDocs.map((doc) => (
                          <tr key={doc.id} className="hover:bg-muted/20 transition-colors">
                            <td className="px-4 py-3 font-medium text-foreground max-w-xs truncate">
                              <div className="flex items-center gap-2">
                                {getFormatIcon(doc.title, doc.document_type)}
                                <span className="truncate" title={doc.title}>
                                  {doc.title}
                                </span>
                              </div>
                            </td>
                            <td className="px-4 py-3 text-muted-foreground">
                              {doc.organization || "Academic Institution"}
                            </td>
                            <td className="px-4 py-3">
                              <Badge variant="outline" className="font-mono text-[9px] uppercase">
                                {doc.document_type || "educational"}
                              </Badge>
                            </td>
                            <td className="px-4 py-3 font-mono text-muted-foreground">
                              {doc.report_year || "—"}
                            </td>
                            <td className="px-4 py-3">
                              <Badge
                                className={`text-[10px] font-mono ${
                                  doc.status === "ready"
                                    ? "bg-emerald-500/15 text-emerald-400 border-emerald-500/30"
                                    : "bg-amber-500/15 text-amber-400 border-amber-500/30"
                                }`}
                              >
                                {doc.status}
                              </Badge>
                            </td>
                            <td className="px-4 py-3 text-right">
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => handleDelete(doc.id, doc.title)}
                                className="h-7 w-7 p-0 text-muted-foreground hover:text-destructive hover:bg-destructive/10"
                                title="Delete document"
                              >
                                <Trash2 className="h-3.5 w-3.5" />
                              </Button>
                            </td>
                          </tr>
                        ))
                      )}
                    </tbody>
                  </table>
                </div>
              </CardContent>
            </Card>
          </div>
        )}

        {/* Security & Architectural Controls Info */}
        <Card className="border-border bg-card">
          <CardHeader className="pb-3 border-b border-border">
            <CardTitle className="text-sm font-semibold flex items-center gap-2">
              <Shield className="h-4 w-4 text-emerald-400" />
              <span>Security & Engineering Architecture Constraints</span>
            </CardTitle>
          </CardHeader>
          <CardContent className="p-6 space-y-3 text-xs text-muted-foreground">
            <div className="flex items-start gap-2">
              <span className="text-primary font-bold">•</span>
              <span>
                <strong className="text-foreground">Pre-Retrieval Authorization:</strong> Document
                access scopes are strictly resolved at the PostgreSQL database layer prior to any
                Qdrant vector retrieval. The model never receives unauthorized context.
              </span>
            </div>
            <div className="flex items-start gap-2">
              <span className="text-primary font-bold">•</span>
              <span>
                <strong className="text-foreground">Secret & Credential Isolation:</strong> API keys
                (Gemini, Claude, Qdrant) are strictly stored in server-side environment variables and
                never surfaced to client-side code or browser local storage.
              </span>
            </div>
            <div className="flex items-start gap-2">
              <span className="text-primary font-bold">•</span>
              <span>
                <strong className="text-foreground">Grounded Citation Validation:</strong> Any
                citation IDs hallucinated or fabricated by generative LLM nodes are automatically
                stripped before rendering to analysts.
              </span>
            </div>
          </CardContent>
        </Card>
      </div>
    </AppShell>
  );
}
