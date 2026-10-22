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
  Compass,
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

  const startRef = React.useRef<number>(0);

  // If newly streaming, open automatically
  React.useEffect(() => {
    if (isStreaming) {
      setIsOpen(true);
    }
  }, [isStreaming]);

  // Live timer tick during streaming — only restarts when isStreaming toggles
  // durationSeconds is intentionally excluded from deps to avoid restarting the
  // interval on every parent re-render (which caused the infinite update loop).
  React.useEffect(() => {
    if (!isStreaming) {
      return;
    }
    startRef.current = Date.now();
    const interval = setInterval(() => {
      setLiveSeconds(
        Math.max(0.1, Number(((Date.now() - startRef.current) / 1000).toFixed(1)))
      );
    }, 100);
    return () => clearInterval(interval);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isStreaming]);

  // Sync liveSeconds to the final durationSeconds once streaming ends
  React.useEffect(() => {
    if (!isStreaming && durationSeconds > 0) {
      setLiveSeconds(durationSeconds);
    }
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
      case "contextualize_query":
        return <Compass className="h-3.5 w-3.5 text-sky-500 shrink-0" />;
      case "classify_query":
        return <Brain className="h-3.5 w-3.5 text-violet-500 shrink-0" />;
      case "extract_constraints":
        return <Layers className="h-3.5 w-3.5 text-indigo-500 shrink-0" />;
      case "retrieve":
      case "retrieval_started":
      case "retrieval_completed":
      case "retrieve_comparison":
        return <Search className="h-3.5 w-3.5 text-sky-500 shrink-0" />;
      case "assess_evidence":
        return <Sparkles className="h-3.5 w-3.5 text-amber-500 shrink-0" />;
      case "generate":
      case "generation_started":
        return <FileText className="h-3.5 w-3.5 text-emerald-500 shrink-0" />;
      case "validate_citations":
        return <ShieldCheck className="h-3.5 w-3.5 text-emerald-500 shrink-0" />;
      default:
        return <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500 shrink-0" />;
    }
  };

  // Determine active pipeline milestone
  const hasStep = (name: string) => steps.some((s) => s.step.includes(name));
  const stages = [
    { id: "classify", label: "Intent", done: hasStep("classify") || hasStep("contextualize") },
    { id: "retrieve", label: "Search", done: hasStep("retrieve") },
    { id: "assess", label: "Evaluate", done: hasStep("assess") },
    { id: "generate", label: "Synthesize", done: hasStep("generate") || hasStep("validate") },
  ];

  return (
    <div
      className={`mb-3.5 rounded-xl border transition-all duration-300 overflow-hidden shadow-xs ${
        isStreaming
          ? "border-primary/40 bg-gradient-to-b from-primary/[0.04] to-card ring-1 ring-primary/20 shadow-primary/5 shadow-md"
          : "border-border/80 bg-card/60 hover:border-border"
      }`}
    >
      {/* Header bar / Toggle */}
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center justify-between px-3.5 py-2.5 text-xs text-foreground/80 hover:text-foreground hover:bg-accent/30 transition-colors select-none"
      >
        <div className="flex items-center gap-2.5 truncate">
          {isStreaming ? (
            <div className="flex items-center gap-2 text-primary font-medium truncate">
              <span className="relative flex h-2 w-2 shrink-0">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-primary opacity-75" />
                <span className="relative inline-flex rounded-full h-2 w-2 bg-primary" />
              </span>
              <Sparkles className="h-3.5 w-3.5 animate-pulse shrink-0" />
              <span className="truncate">
                {activeStep ? activeStep.title : "Researching & synthesizing response..."}
              </span>
            </div>
          ) : (
            <div className="flex items-center gap-2 font-medium text-foreground/90">
              <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600 dark:text-emerald-400 shrink-0" />
              <span>
                Thought for {timeDisplay || "a few seconds"}
                {stepCount > 0 && ` • ${stepCount} research steps`}
              </span>
            </div>
          )}
        </div>

        <div className="flex items-center gap-2 shrink-0 text-muted-foreground ml-2">
          {isStreaming && (
            <span className="font-mono text-[11px] font-semibold text-primary flex items-center gap-1 bg-primary/15 border border-primary/25 px-2 py-0.5 rounded-full animate-pulse">
              <Clock className="h-3 w-3" />
              {timeDisplay}
            </span>
          )}
          <span className="p-0.5 rounded hover:bg-muted text-muted-foreground transition-colors">
            {isOpen ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
          </span>
        </div>
      </button>

      {/* Live Pipeline Milestone Track */}
      {isStreaming && (
        <div className="px-3.5 pb-2 pt-0.5 flex items-center gap-1.5 border-b border-border/40 text-[10px]">
          {stages.map((stage, idx) => (
            <React.Fragment key={stage.id}>
              <div
                className={`flex items-center gap-1 px-2 py-0.5 rounded-full font-medium transition-colors ${
                  stage.done
                    ? "bg-primary/15 text-primary border border-primary/25"
                    : "bg-muted/60 text-muted-foreground border border-transparent"
                }`}
              >
                <span className="h-1.5 w-1.5 rounded-full bg-current" />
                <span>{stage.label}</span>
              </div>
              {idx < stages.length - 1 && (
                <span className="text-muted-foreground/40 font-mono text-[9px]">→</span>
              )}
            </React.Fragment>
          ))}
        </div>
      )}

      {/* Accordion detail list */}
      {isOpen && (
        <div className="border-t border-border/50 px-3.5 py-3 bg-muted/20 space-y-2.5 text-xs">
          {steps.map((st, idx) => {
            const isInProg = st.status === "in_progress";

            return (
              <div
                key={`${st.step}-${idx}`}
                className={`flex items-start gap-2.5 rounded-lg p-2 transition-all ${
                  isInProg
                    ? "bg-primary/[0.06] border border-primary/25 shadow-xs"
                    : "hover:bg-accent/40"
                }`}
              >
                <div className="mt-0.5 shrink-0">{getStepIcon(st.step, st.status)}</div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between gap-2">
                    <span
                      className={`font-semibold text-xs ${
                        isInProg ? "text-primary font-bold" : "text-foreground"
                      }`}
                    >
                      {st.title}
                    </span>
                    {isInProg && (
                      <span className="text-[10px] font-mono uppercase bg-primary/20 text-primary px-1.5 py-0.5 rounded-full font-semibold animate-pulse">
                        processing
                      </span>
                    )}
                  </div>
                  {st.detail && (
                    <p className="text-[11px] text-muted-foreground leading-relaxed mt-0.5 font-sans">
                      {st.detail}
                    </p>
                  )}
                </div>
              </div>
            );
          })}

          {isStreaming && steps.length === 0 && (
            <div className="flex items-center gap-2 py-2 text-muted-foreground italic text-xs">
              <Loader2 className="h-3.5 w-3.5 animate-spin text-primary" />
              <span>Connecting to RAG agents & analyzing question scope...</span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
