"use client";

import * as React from "react";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ExternalLink, HelpCircle, Eye, ShieldAlert, CheckCircle2, ThumbsUp, MessageSquareQuote, FileQuestion } from "lucide-react";
import { VulnerabilityTableRow } from "@/lib/api";

interface UserCentricVulnerabilitiesProps {
  rows?: VulnerabilityTableRow[];
}

export function UserCentricVulnerabilities({ rows }: UserCentricVulnerabilitiesProps) {
  const defaultRows: VulnerabilityTableRow[] = [
    {
      reveal: "Binary Feedback (+/-) & Corrections",
      measures: "Completeness & Accuracy",
      capture_method:
        "User thumbs-up/down button on every response. Thumbs-down prompts with 'What was missing or incorrect?' to capture vector DB gaps.",
      current_status: "Active live feedback loop",
      risk_assessment: "Optimal",
      metric_value: 0,
      metric_unit: "ratings",
    },
    {
      reveal: "'I Don't Know' Abstention Rate",
      measures: "Vector Database Knowledge Gaps",
      capture_method:
        "Agent says: 'I cannot find that in the provided documentation.' Tracks frequency of this phrase to identify unindexed topics.",
      current_status: "Active Tracking",
      risk_assessment: "Comprehensive Coverage",
      metric_value: 0,
      metric_unit: "triggers",
    },
    {
      reveal: "Citation clicks",
      measures: "Trust & Completeness",
      capture_method:
        "Track if users actually click the source links your RAG provides. If they don't, the answer was complete enough.",
      current_status: "Active Tracking via Telemetry Stream",
      risk_assessment: "Optimal",
      metric_value: 0,
      metric_unit: "clicks",
    },
    {
      reveal: "Fallback triggers",
      measures: "Database Gaps",
      capture_method:
        "Count how many times users force the agent into an abstention or ungrounded fallback.",
      current_status: "Measured via Grounding & Abstained Counters",
      risk_assessment: "Healthy",
      metric_value: 0,
      metric_unit: "fallbacks",
    },
    {
      reveal: "Over-the-shoulder UX",
      measures: "Hallucinations",
      capture_method:
        "Watch live users interact with the tool without intervening. Note where they hesitate or submit frustration keywords.",
      current_status: "Anonymized session logging with 10+ turn flags",
      risk_assessment: "Monitoring Active",
      metric_value: 0,
      metric_unit: "struggle sessions",
    },
  ];

  const displayRows = rows && rows.length > 0 ? rows : defaultRows;

  return (
    <Card className="border-border bg-card shadow-xs">
      <CardHeader className="pb-3 border-b border-border">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
          <div>
            <CardTitle className="text-sm font-semibold flex items-center gap-2 text-foreground">
              <ShieldAlert className="h-4 w-4 text-primary" />
              <span>Direct Comparison: Table of User-Centric Vulnerabilities</span>
            </CardTitle>
            <p className="text-xs text-muted-foreground mt-0.5">
              While you don&apos;t trust synthetic test suites, you can use these user-driven metrics to measure real production success.
            </p>
          </div>
          <Badge variant="outline" className="text-[10px] font-mono py-0.5 self-start sm:self-auto border-primary/30 text-primary">
            User-Driven Telemetry
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="p-0 overflow-x-auto">
        <table className="w-full text-xs text-left border-collapse">
          <thead>
            <tr className="border-b border-border bg-muted/50 text-foreground font-semibold">
              <th scope="col" className="py-3 px-4 font-semibold">What Real Users Reveal</th>
              <th scope="col" className="py-3 px-4 font-semibold">What It Measures</th>
              <th scope="col" className="py-3 px-4 font-semibold">How to Capture It</th>
              <th scope="col" className="py-3 px-4 font-semibold">Production Status / Live Tracking</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border/60">
            {displayRows.map((row, idx) => {
              const isFeedback = row.reveal.toLowerCase().includes("feedback");
              const isIdk = row.reveal.toLowerCase().includes("know") || row.reveal.toLowerCase().includes("abstention");
              const isClicks = row.reveal.toLowerCase().includes("citation");
              const isFallback = row.reveal.toLowerCase().includes("fallback");
              const isUx = row.reveal.toLowerCase().includes("ux");

              return (
                <tr key={`${row.reveal}-${idx}`} className="hover:bg-accent/40 transition-colors">
                  <td className="py-3.5 px-4 font-semibold text-foreground align-top">
                    <div className="flex items-center gap-2">
                      <div className="p-1 rounded bg-primary/10 text-primary">
                        {isFeedback ? (
                          <ThumbsUp className="h-3.5 w-3.5 text-emerald-600 dark:text-emerald-400" />
                        ) : isIdk ? (
                          <FileQuestion className="h-3.5 w-3.5 text-amber-600 dark:text-amber-400" />
                        ) : isClicks ? (
                          <ExternalLink className="h-3.5 w-3.5" />
                        ) : isFallback ? (
                          <HelpCircle className="h-3.5 w-3.5" />
                        ) : (
                          <Eye className="h-3.5 w-3.5" />
                        )}
                      </div>
                      <span className="text-sm font-medium">{row.reveal}</span>
                    </div>
                  </td>
                  <td className="py-3.5 px-4 font-medium text-foreground align-top">
                    <Badge variant="secondary" className="font-medium text-[11px] py-0.5">
                      {row.measures}
                    </Badge>
                  </td>
                  <td className="py-3.5 px-4 text-muted-foreground leading-relaxed max-w-sm align-top">
                    {row.capture_method}
                  </td>
                  <td className="py-3.5 px-4 align-top">
                    <div className="space-y-1">
                      <div className="font-mono text-foreground font-medium text-[11px]">
                        {row.current_status}
                      </div>
                      <div className="flex items-center gap-1.5 text-[10px] text-emerald-600 dark:text-emerald-400">
                        <CheckCircle2 className="h-3 w-3" />
                        <span>Assessment: {row.risk_assessment}</span>
                      </div>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </CardContent>
    </Card>
  );
}
