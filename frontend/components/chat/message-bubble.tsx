"use client";

import * as React from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { User, Bot, AlertTriangle, ShieldCheck } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { CitationCard } from "@/components/citations/citation-card";
import { ThinkingProcess } from "@/components/chat/thinking-process";
import { AgentStep, ChatCitationItem } from "@/lib/types";

export interface MessageBubbleProps {
  role: "user" | "assistant";
  content: string;
  grounded?: boolean;
  abstained?: boolean;
  citations?: ChatCitationItem[];
  steps?: AgentStep[];
  durationSeconds?: number;
  onSelectCitation?: (citation: ChatCitationItem) => void;
  isStreaming?: boolean;
}

function cleanMarkdown(raw: string): string {
  if (!raw) return "";
  // Strip raw long bracketed UUID citations from body text (e.g. 【573f1d11-...】 or [573f1d11-...])
  return raw
    .replace(/【[0-9a-fA-F-]{36}】/g, "")
    .replace(/\[[0-9a-fA-F-]{36}\]/g, "")
    .trim();
}

export function MessageBubble({
  role,
  content,
  grounded,
  abstained,
  citations = [],
  steps = [],
  durationSeconds = 0,
  onSelectCitation,
  isStreaming = false,
}: MessageBubbleProps) {
  const isUser = role === "user";
  const cleanedText = cleanMarkdown(content);

  return (
    <div
      className={`flex items-start gap-3.5 py-4 ${
        isUser ? "justify-end" : "justify-start border-b border-border/40"
      }`}
    >
      {!isUser && (
        <div className="h-8 w-8 rounded-lg bg-primary/10 border border-primary/20 flex items-center justify-center text-primary shrink-0 mt-0.5 shadow-sm">
          <Bot className="h-4 w-4" />
        </div>
      )}

      <div className={`space-y-3 max-w-3xl ${isUser ? "text-right" : "text-left flex-1 min-w-0"}`}>
        {/* Author / Status Header */}
        <div className={`flex items-center gap-2 text-xs ${isUser ? "justify-end" : "justify-start"}`}>
          <span className="font-semibold text-foreground">
            {isUser ? "Analyst" : "RAG Assistant"}
          </span>
          {!isUser && grounded && (
            <Badge variant="outline" className="text-[10px] text-emerald-700 dark:text-emerald-400 border-emerald-500/40 gap-1 py-0 font-medium">
              <ShieldCheck className="h-3 w-3" /> Grounded
            </Badge>
          )}
          {!isUser && abstained && (
            <Badge variant="secondary" className="text-[10px] text-amber-700 dark:text-amber-400 border-amber-500/40 gap-1 py-0 font-medium">
              <AlertTriangle className="h-3 w-3" /> Abstained (Insufficient Evidence)
            </Badge>
          )}
        </div>

        {/* Claude-style Thinking / Process Accordion */}
        {!isUser && (steps.length > 0 || isStreaming) && (
          <ThinkingProcess
            steps={steps}
            isStreaming={isStreaming}
            durationSeconds={durationSeconds}
          />
        )}

        {/* Content Box (render if content exists or if user) */}
        {(isUser || cleanedText.length > 0 || !isStreaming) && (
          <div
            className={`rounded-xl p-4 text-sm leading-relaxed ${
              isUser
                ? "bg-primary text-primary-foreground font-sans inline-block shadow-sm"
                : "bg-card border border-border text-foreground font-sans shadow-sm"
            }`}
          >
            {isUser ? (
              <div className="whitespace-pre-wrap">{content}</div>
            ) : (
              <div className="prose prose-sm max-w-none space-y-2 text-foreground">
                <ReactMarkdown
                  remarkPlugins={[remarkGfm]}
                components={{
                  p: ({ children }) => <p className="mb-2.5 last:mb-0 leading-relaxed text-foreground font-normal">{children}</p>,
                  h1: ({ children }) => <h1 className="text-base font-bold text-foreground mt-3 mb-2 first:mt-0 tracking-tight">{children}</h1>,
                  h2: ({ children }) => <h2 className="text-sm font-bold text-foreground mt-3 mb-1.5 first:mt-0 tracking-tight">{children}</h2>,
                  h3: ({ children }) => <h3 className="text-xs font-bold text-foreground uppercase tracking-wider mt-2.5 mb-1 text-primary">{children}</h3>,
                  ul: ({ children }) => <ul className="list-disc pl-5 mb-2.5 space-y-1 text-foreground font-normal">{children}</ul>,
                  ol: ({ children }) => <ol className="list-decimal pl-5 mb-2.5 space-y-1 text-foreground font-normal">{children}</ol>,
                  li: ({ children }) => <li className="leading-relaxed text-foreground">{children}</li>,
                  strong: ({ children }) => <strong className="font-bold text-foreground">{children}</strong>,
                  blockquote: ({ children }) => (
                    <blockquote className="border-l-2 border-primary pl-3 py-1 my-2 text-foreground/90 italic bg-accent/30 rounded-r">
                      {children}
                    </blockquote>
                  ),
                  table: ({ children }) => (
                    <div className="overflow-x-auto my-3 rounded-lg border border-border">
                      <table className="w-full text-xs text-left border-collapse">{children}</table>
                    </div>
                  ),
                  thead: ({ children }) => <thead className="bg-muted text-foreground font-semibold border-b border-border">{children}</thead>,
                  tbody: ({ children }) => <tbody className="divide-y divide-border/40 text-foreground">{children}</tbody>,
                  tr: ({ children }) => <tr className="hover:bg-accent/30 transition-colors">{children}</tr>,
                  th: ({ children }) => <th className="p-2.5 font-semibold text-foreground">{children}</th>,
                  td: ({ children }) => <td className="p-2.5 text-foreground font-normal">{children}</td>,
                  code: ({ children }) => (
                    <code className="bg-muted text-foreground font-semibold px-1.5 py-0.5 rounded text-xs font-mono border border-border">
                      {children}
                    </code>
                  ),
                }}
              >
                {cleanedText}
              </ReactMarkdown>
              {isStreaming && (
                <span className="inline-block w-2 h-4 ml-1 bg-primary animate-pulse align-middle" />
              )}
            </div>
          )}
        </div>
        )}

        {/* Citations List (Phase 14 & 15) */}
        {!isUser && citations.length > 0 && (
          <div className="pt-2 space-y-2">
            <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider block">
              Source Citations & Provenance ({citations.length})
            </span>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              {citations.map((c, idx) => (
                <CitationCard
                  key={`${c.chunk_id || "cit"}-${idx}`}
                  citation={c}
                  index={idx}
                  onSelect={(cit) => onSelectCitation?.(cit)}
                />
              ))}
            </div>
          </div>
        )}
      </div>

      {isUser && (
        <div className="h-8 w-8 rounded-lg bg-accent border border-border flex items-center justify-center text-foreground shrink-0 mt-0.5 shadow-sm">
          <User className="h-4 w-4" />
        </div>
      )}
    </div>
  );
}
