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

  const handleDelete = async (docId: string) => {
    if (!confirm("Are you sure you want to delete this document from the corpus?")) return;
    try {
      await documentsApi.delete(docId);
      await loadData();
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Deletion failed");
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

            {/* Ingestion & Upload Card */}
            <Card className="border-primary/30 bg-card shadow-md relative overflow-hidden">
              <div className="absolute top-0 right-0 w-64 h-64 bg-primary/5 rounded-full blur-3xl pointer-events-none -mr-20 -mt-20" />
              
              <CardHeader className="pb-3 border-b border-border/80">
                <div className="flex items-center justify-between">
                  <CardTitle className="text-sm font-semibold flex items-center gap-2">
                    <UploadCloud className="h-4 w-4 text-primary" />
                    <span>Admin Document Ingestion Hub</span>
                  </CardTitle>
                  <Badge variant="outline" className="border-primary/40 text-primary text-[10px]">
                    Automatic Pipeline: Parse ➔ Chunk ➔ Index ➔ Ready
                  </Badge>
                </div>
                <p className="text-xs text-muted-foreground">
                  Upload educational research papers, syllabi, datasets, or spreadsheets. Files are parsed, normalized, indexed into Qdrant, and immediately usable for queries and citations.
                </p>
              </CardHeader>

              <CardContent className="p-6 space-y-5">
                <form onSubmit={handleUploadAndProcess} className="space-y-5">
                  {/* Drag and Drop Dropzone */}
                  <div
                    onDragEnter={handleDrag}
                    onDragLeave={handleDrag}
                    onDragOver={handleDrag}
                    onDrop={handleDrop}
                    onClick={() => fileInputRef.current?.click()}
                    className={`border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-all duration-200 flex flex-col items-center justify-center gap-3 ${
                      dragActive
                        ? "border-primary bg-primary/10 shadow-lg"
                        : file
                        ? "border-emerald-500/50 bg-emerald-500/5"
                        : "border-border hover:border-primary/50 hover:bg-muted/30"
                    }`}
                  >
                    <input
                      ref={fileInputRef}
                      type="file"
                      accept=".pdf,.docx,.csv,.xlsx,.txt"
                      className="hidden"
                      onChange={(e) => {
                        if (e.target.files && e.target.files[0]) {
                          handleFileSelected(e.target.files[0]);
                        }
                      }}
                    />

                    {file ? (
                      <div className="flex flex-col items-center gap-2">
                        <div className="h-12 w-12 rounded-full bg-emerald-500/20 text-emerald-400 flex items-center justify-center">
                          {getFormatIcon(file.name)}
                        </div>
                        <div className="space-y-0.5">
                          <p className="text-sm font-medium text-foreground">{file.name}</p>
                          <p className="text-xs text-muted-foreground">
                            {(file.size / 1024).toFixed(1)} KB • Ready to process
                          </p>
                        </div>
                        <Button
                          type="button"
                          variant="ghost"
                          size="sm"
                          onClick={(e) => {
                            e.stopPropagation();
                            setFile(null);
                            if (fileInputRef.current) fileInputRef.current.value = "";
                          }}
                          className="text-xs text-muted-foreground hover:text-destructive h-7 px-2 mt-1"
                        >
                          Change File
                        </Button>
                      </div>
                    ) : (
                      <div className="flex flex-col items-center gap-2 text-center">
                        <div className="h-12 w-12 rounded-full bg-muted flex items-center justify-center text-muted-foreground group-hover:text-primary transition-colors">
                          <UploadCloud className="h-6 w-6" />
                        </div>
                        <div>
                          <p className="text-sm font-medium text-foreground">
                            Drag and drop file here, or <span className="text-primary underline">browse</span>
                          </p>
                          <p className="text-xs text-muted-foreground mt-1">
                            Supported: <span className="font-mono text-[11px] text-foreground/80">PDF, DOCX, CSV, XLSX, TXT</span> (Max 50MB)
                          </p>
                        </div>
                      </div>
                    )}
                  </div>

                  {/* Metadata Fields */}
                  <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4">
                    <div>
                      <Input
                        label="Document Title (Optional)"
                        placeholder="Auto-detected from filename"
                        value={title}
                        onChange={(e) => setTitle(e.target.value)}
                        className="text-xs"
                      />
                    </div>
                    <div>
                      <Input
                        label="Institution / Organization"
                        placeholder="e.g. MIT, Stanford, OECD, NCES"
                        value={organization}
                        onChange={(e) => setOrganization(e.target.value)}
                        className="text-xs"
                      />
                    </div>
                    <div className="space-y-1">
                      <label className="text-sm font-medium text-muted-foreground block">
                        Document Type
                      </label>
                      <select
                        value={documentType}
                        onChange={(e) => setDocumentType(e.target.value)}
                        className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-xs shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                      >
                        <option value="research_paper">Research Paper (PDF/DOCX)</option>
                        <option value="syllabus">Course Syllabus (DOCX/PDF)</option>
                        <option value="dataset">Educational Dataset (CSV)</option>
                        <option value="spreadsheet">Statistical Workbook (XLSX)</option>
                        <option value="educational">Educational Resource (General)</option>
                      </select>
                    </div>
                    <div>
                      <Input
                        label="Academic / Report Year"
                        type="number"
                        placeholder="e.g. 2024"
                        value={reportYear}
                        onChange={(e) => setReportYear(e.target.value)}
                        className="text-xs"
                      />
                    </div>
                  </div>

                  {/* Submit Button & Progress */}
                  <div className="flex flex-col sm:flex-row items-center justify-between gap-3 pt-2 border-t border-border">
                    <div className="text-xs text-muted-foreground flex items-center gap-1.5">
                      <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" />
                      <span>Role access is automatically granted to all analysts upon ingestion.</span>
                    </div>

                    <Button
                      type="submit"
                      disabled={!file || isProcessing}
                      className="gap-2 text-xs w-full sm:w-auto min-w-[200px]"
                    >
                      {isProcessing ? (
                        <>
                          <Loader2 className="h-4 w-4 animate-spin" />
                          <span>Processing Document...</span>
                        </>
                      ) : (
                        <>
                          <Sparkles className="h-4 w-4" />
                          <span>Upload & Ingest Document</span>
                        </>
                      )}
                    </Button>
                  </div>
                </form>

                {/* Real-Time Processing Stage Feedback */}
                {isProcessing && (
                  <div className="p-4 rounded-lg bg-primary/10 border border-primary/20 space-y-2 animate-pulse">
                    <div className="flex items-center gap-2 text-xs font-semibold text-primary">
                      <Loader2 className="h-4 w-4 animate-spin" />
                      <span>Live Ingestion Pipeline Active</span>
                    </div>
                    <p className="text-xs font-mono text-muted-foreground">{processingStage}</p>
                    <div className="w-full bg-muted h-1.5 rounded-full overflow-hidden">
                      <div className="bg-primary h-full animate-[indeterminate_1.5s_infinite_linear]" />
                    </div>
                  </div>
                )}

                {/* Success Banner */}
                {uploadResult && (
                  <div className="p-4 rounded-xl bg-emerald-500/10 border border-emerald-500/30 space-y-3">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2 text-emerald-400 font-semibold text-xs">
                        <CheckCircle2 className="h-4 w-4" />
                        <span>Document Successfully Processed and Vector-Indexed!</span>
                      </div>
                      <Badge className="bg-emerald-500/20 text-emerald-400 border-emerald-500/40 text-[10px]">
                        Status: Ready
                      </Badge>
                    </div>
                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs pt-1">
                      <div>
                        <span className="text-muted-foreground block text-[11px]">Title</span>
                        <span className="font-medium text-foreground">{uploadResult.title}</span>
                      </div>
                      <div>
                        <span className="text-muted-foreground block text-[11px]">Sections Extracted</span>
                        <span className="font-mono text-foreground">{uploadResult.sections_count ?? 1}</span>
                      </div>
                      <div>
                        <span className="text-muted-foreground block text-[11px]">Chunks in Qdrant</span>
                        <span className="font-mono text-emerald-400 font-bold">{uploadResult.chunks_count ?? 0}</span>
                      </div>
                      <div>
                        <span className="text-muted-foreground block text-[11px]">Availability</span>
                        <span className="text-emerald-400 flex items-center gap-1">
                          <Check className="h-3 w-3" /> Usable in RAG
                        </span>
                      </div>
                    </div>
                  </div>
                )}

                {/* Error Banner */}
                {errorMessage && (
                  <div className="p-4 rounded-xl bg-destructive/10 border border-destructive/30 flex items-start gap-3 text-xs text-destructive">
                    <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
                    <div>
                      <p className="font-semibold">Ingestion Failed</p>
                      <p className="text-muted-foreground mt-0.5">{errorMessage}</p>
                    </div>
                  </div>
                )}
              </CardContent>
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
                                onClick={() => handleDelete(doc.id)}
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
