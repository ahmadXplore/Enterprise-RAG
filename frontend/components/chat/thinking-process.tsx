"use client";

import * as React from "react";
import {
  ChevronDown,
  ChevronRight,
  CheckCircle2,
  Loader2,
  Sparkles,
  Search,
  Layers,
  Brain,
  ShieldCheck,
  FileText,
  Clock,
} from "lucide-react";
import { AgentStep } from "@/lib/types";

export interface ThinkingProcessProps {
  steps: AgentStep[];
  isStreaming: boolean;
  durationSeconds?: number;
}

export function ThinkingProcess({
  steps,
  isStreaming,
  durationSeconds = 0,
}: ThinkingProcessProps) {
  // During streaming, open by default so user sees live progress; after completion, collapsed by default
  const [isOpen, setIsOpen] = React.useState(isStreaming);
  const [liveSeconds, setLiveSeconds] = React.useState(durationSeconds);

  // If newly streaming, open automatically
  React.useEffect(() => {
    if (isStreaming) {
      setIsOpen(true);
    }
  }, [isStreaming]);

  // Live timer tick during streaming
  React.useEffect(() => {
    if (!isStreaming) {
      setLiveSeconds(durationSeconds);
      return;
    }
    const start = Date.now();
    const interval = setInterval(() => {
      setLiveSeconds(Math.max(0.1, Number(((Date.now() - start) / 1000).toFixed(1))));
    }, 100);
    return () => clearInterval(interval);
  }, [isStreaming, durationSeconds]);

  if (steps.length === 0 && !isStreaming) {
    return null;
  }

  // Active or latest step
  const activeStep = steps.find((s) => s.status === "in_progress") || steps[steps.length - 1];
  const stepCount = steps.length;
  const timeDisplay = isStreaming
    ? `${liveSeconds.toFixed(1)}s`
    : durationSeconds > 0
    ? `${durationSeconds.toFixed(1)}s`
    : liveSeconds > 0
    ? `${liveSeconds.toFixed(1)}s`
    : "";

  const getStepIcon = (nodeName: string, status: string) => {
    if (status === "in_progress") {
      return <Loader2 className="h-3.5 w-3.5 animate-spin text-primary shrink-0" />;
    }
    switch (nodeName) {
      case "classify_query":
        return <Brain className="h-3.5 w-3.5 text-emerald-600 dark:text-emerald-400 shrink-0" />;
      case "extract_constraints":
        return <Layers className="h-3.5 w-3.5 text-emerald-600 dark:text-emerald-400 shrink-0" />;
      case "retrieve":
      case "retrieval_started":
      case "retrieval_completed":
        return <Search className="h-3.5 w-3.5 text-sky-600 dark:text-sky-400 shrink-0" />;
      case "assess_evidence":
        return <Sparkles className="h-3.5 w-3.5 text-amber-600 dark:text-amber-400 shrink-0" />;
      case "generate":
      case "generation_started":
        return <FileText className="h-3.5 w-3.5 text-indigo-600 dark:text-indigo-400 shrink-0" />;
      case "validate_citations":
        return <ShieldCheck className="h-3.5 w-3.5 text-emerald-600 dark:text-emerald-400 shrink-0" />;
      default:
        return <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600 dark:text-emerald-400 shrink-0" />;
    }
  };

  return (
    <div className="mb-3.5 rounded-lg border border-border bg-muted/40 transition-all overflow-hidden shadow-xs">
      {/* Header bar / Toggle */}
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center justify-between px-3 py-2 text-xs text-foreground/80 hover:text-foreground hover:bg-accent/40 transition-colors select-none"
      >
        <div className="flex items-center gap-2 truncate">
          {isStreaming ? (
            <div className="flex items-center gap-1.5 text-primary font-medium">
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-primary opacity-75" />
                <span className="relative inline-flex rounded-full h-2 w-2 bg-primary" />
              </span>
              <Sparkles className="h-3.5 w-3.5 animate-pulse" />
              <span className="truncate">
                {activeStep ? activeStep.title : "Researching & synthesizing..."}
              </span>
            </div>
          ) : (
            <div className="flex items-center gap-1.5 font-medium text-foreground/85">
              <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600 dark:text-emerald-400" />
              <span>
                Thought for {timeDisplay || "a few seconds"}
                {stepCount > 0 && ` • ${stepCount} research steps`}
              </span>
            </div>
          )}
        </div>

        <div className="flex items-center gap-2 shrink-0 text-muted-foreground ml-2">
          {isStreaming && (
            <span className="font-mono text-[11px] text-primary/90 flex items-center gap-1 bg-primary/10 px-1.5 py-0.5 rounded">
              <Clock className="h-3 w-3" />
              {timeDisplay}
            </span>
          )}
          {isOpen ? (
            <ChevronDown className="h-3.5 w-3.5" />
          ) : (
            <ChevronRight className="h-3.5 w-3.5" />
          )}
        </div>
      </button>

      {/* Accordion detail list */}
      {isOpen && (
        <div className="border-t border-border/60 px-3.5 py-2.5 bg-card/50 space-y-2.5 text-xs">
          {steps.map((st, idx) => {
            const isLast = idx === steps.length - 1;
            const isInProg = st.status === "in_progress";

            return (
              <div key={`${st.step}-${idx}`} className="flex items-start gap-2.5 group">
                <div className="mt-0.5">{getStepIcon(st.step, st.status)}</div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between gap-2">
                    <span
                      className={`font-semibold ${
                        isInProg
                          ? "text-primary animate-pulse"
                          : "text-foreground"
                      }`}
                    >
                      {st.title}
                    </span>
                    {isInProg && (
                      <span className="text-[10px] font-mono uppercase bg-primary/15 text-primary px-1.5 py-0.2 rounded font-medium">
                        running
                      </span>
                    )}
                  </div>
                  {st.detail && (
                    <p className="text-[11px] text-foreground/75 leading-relaxed mt-0.5 font-sans">
                      {st.detail}
                    </p>
                  )}
                </div>
              </div>
            );
          })}

          {isStreaming && steps.length === 0 && (
            <div className="flex items-center gap-2 py-1 text-muted-foreground italic text-xs">
              <Loader2 className="h-3 w-3 animate-spin text-primary" />
              <span>Initializing research agent pipeline...</span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
