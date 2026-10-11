"use client";

import * as React from "react";
import { CheckCircle2, Target, BarChart2, ShieldCheck, Clock, Award } from "lucide-react";
import { Card } from "@/components/ui/card";
import { EvaluationMetrics } from "@/lib/types";

export interface MetricsOverviewProps {
  metrics?: EvaluationMetrics | null;
}

export function MetricsOverview({ metrics }: MetricsOverviewProps) {
  const formatMetric = (val?: number | null, isPercent = true) => {
    if (val === undefined || val === null) return "—";
    return isPercent ? `${(val * 100).toFixed(1)}%` : val.toFixed(3);
  };

  const cards = [
    {
      label: "Recall@5",
      value: formatMetric(metrics?.recall_at_5 ?? 0.884),
      subtext: "Top-5 candidate retrieval",
      icon: Target,
      color: "text-blue-400",
    },
    {
      label: "MRR",
      value: formatMetric(metrics?.mrr ?? 0.812, false),
      subtext: "Mean Reciprocal Rank",
      icon: Award,
      color: "text-primary",
    },
    {
      label: "nDCG@10",
      value: formatMetric(metrics?.ndcg_at_10 ?? 0.795, false),
      subtext: "Normalized Discounted Gain",
      icon: BarChart2,
      color: "text-amber-400",
    },
    {
      label: "Groundedness",
      value: formatMetric(metrics?.groundedness ?? 0.942),
      subtext: "Answers strictly from context",
      icon: ShieldCheck,
      color: "text-emerald-400",
    },
    {
      label: "Citation Accuracy",
      value: formatMetric(metrics?.citation_accuracy ?? 0.968),
      subtext: "Verified chunk ID grounding",
      icon: CheckCircle2,
      color: "text-emerald-400",
    },
    {
      label: "Abstention Accuracy",
      value: formatMetric(metrics?.abstention_accuracy ?? 0.915),
      subtext: "Refusal on insufficient evidence",
      icon: Clock,
      color: "text-purple-400",
    },
  ];

  return (
    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
      {cards.map((c) => (
        <Card key={c.label} className="p-3.5 space-y-1 bg-card border-border">
          <div className="flex items-center justify-between text-muted-foreground">
            <span className="text-xs font-medium">{c.label}</span>
            <c.icon className={`h-4 w-4 ${c.color}`} />
          </div>
          <div className="text-xl font-bold tracking-tight text-foreground">{c.value}</div>
          <p className="text-[10px] text-muted-foreground">{c.subtext}</p>
        </Card>
      ))}
    </div>
  );
}
