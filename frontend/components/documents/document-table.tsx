"use client";

import * as React from "react";
import Link from "next/link";
import { ExternalLink, Play, CheckCircle2, Clock } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { DocumentRead } from "@/lib/types";
import { isAdmin } from "@/lib/auth";

export interface DocumentTableProps {
  documents: DocumentRead[];
  onIngest?: (docId: string) => void;
  ingestingIds?: Set<string>;
}

export function DocumentTable({ documents, onIngest, ingestingIds = new Set() }: DocumentTableProps) {
  const admin = isAdmin();

  return (
    <div className="rounded-lg border border-border bg-card overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs">
          <thead className="bg-muted/70 border-b border-border text-foreground uppercase tracking-wider font-bold">
            <tr>
              <th scope="col" className="px-4 py-3">Document Title</th>
              <th scope="col" className="px-4 py-3">Organization</th>
              <th scope="col" className="px-4 py-3">Year</th>
              <th scope="col" className="px-4 py-3">Type</th>
              <th scope="col" className="px-4 py-3">Status</th>
              <th scope="col" className="px-4 py-3 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {documents.map((doc) => {
              const isIngesting = ingestingIds.has(doc.id);
              return (
                <tr key={doc.id} className="hover:bg-accent/30 transition-colors">
                  <td className="px-4 py-3.5 font-medium text-foreground">
                    <Link
                      href={`/documents/${doc.id}`}
                      className="hover:text-primary transition-colors flex items-center gap-1.5"
                    >
                      <span className="truncate max-w-sm">{doc.title}</span>
                      <ExternalLink className="h-3 w-3 text-muted-foreground shrink-0" />
                    </Link>
                  </td>
                  <td className="px-4 py-3.5 text-muted-foreground">{doc.organization || "—"}</td>
                  <td className="px-4 py-3.5 text-muted-foreground">{doc.report_year || "—"}</td>
                  <td className="px-4 py-3.5">
                    <Badge variant="outline" className="text-[10px] font-mono">
                      {doc.document_type}
                    </Badge>
                  </td>
                  <td className="px-4 py-3.5">
                    <Badge
                      variant={
                        doc.status === "ready"
                          ? "success"
                          : doc.status === "registered"
                          ? "outline"
                          : "secondary"
                      }
                      className="capitalize"
                    >
                      {doc.status}
                    </Badge>
                  </td>
                  <td className="px-4 py-3.5 text-right space-x-2">
                    <Link href={`/documents/${doc.id}`}>
                      <Button variant="ghost" size="sm" className="h-7 text-xs px-2">
                        Inspect
                      </Button>
                    </Link>
                    {admin && (
                      <Button
                        variant="outline"
                        size="sm"
                        disabled={isIngesting || doc.status === "ready"}
                        onClick={() => onIngest?.(doc.id)}
                        className="h-7 text-xs px-2 gap-1"
                      >
                        {isIngesting ? (
                          <>
                            <Clock className="h-3 w-3 animate-spin" />
                            <span>Queuing...</span>
                          </>
                        ) : (
                          <>
                            <Play className="h-3 w-3" />
                            <span>Ingest</span>
                          </>
                        )}
                      </Button>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
