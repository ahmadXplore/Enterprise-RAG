"use client";

import * as React from "react";
import { Send, Sparkles, AlertCircle, Square } from "lucide-react";
import { MessageBubble } from "@/components/chat/message-bubble";
import { EvidenceDrawer } from "@/components/citations/evidence-drawer";
import { Button } from "@/components/ui/button";
import { streamChat } from "@/lib/api";
import { AgentStep, ChatCitationItem } from "@/lib/types";

export interface MessageItem {
  id: string;
  role: "user" | "assistant";
  content: string;
  grounded?: boolean;
  abstained?: boolean;
  citations?: ChatCitationItem[];
  steps?: AgentStep[];
  durationSeconds?: number;
}

export interface ChatInterfaceProps {
  conversationId?: string;
}

export function ChatInterface({ conversationId }: ChatInterfaceProps) {
  const [messages, setMessages] = React.useState<MessageItem[]>([
    {
      id: "initial",
      role: "assistant",
      content:
        "Hello. I am your Academic & Educational Research Assistant. Ask any question regarding published papers, educational datasets, global literacy trends, student performance indicators, or course syllabi.",
    },
  ]);
  const [input, setInput] = React.useState("");
  const [submitting, setSubmitting] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  // Streaming live state (for the in-progress assistant message)
  const [streamingId, setStreamingId] = React.useState<string | null>(null);
  const abortRef = React.useRef<AbortController | null>(null);
  const startTimeRef = React.useRef<number>(0);

  // Evidence Drawer
  const [selectedCitation, setSelectedCitation] = React.useState<ChatCitationItem | null>(null);
  const [isDrawerOpen, setIsDrawerOpen] = React.useState(false);

  const messagesEndRef = React.useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  React.useEffect(() => {
    scrollToBottom();
  }, [messages, submitting]);

  const handleStop = () => {
    abortRef.current?.abort();
    setSubmitting(false);
    setStreamingId(null);
  };

  const handleSend = async (textToSend?: string) => {
    const text = (textToSend || input).trim();
    if (!text || submitting) return;

    setError(null);
    setInput("");

    const userMsg: MessageItem = {
      id: crypto.randomUUID(),
      role: "user",
      content: text,
    };

    const assistantId = crypto.randomUUID();
    const emptyAssistant: MessageItem = {
      id: assistantId,
      role: "assistant",
      content: "",
      steps: [],
      citations: [],
      grounded: false,
    };

    setMessages((prev) => [...prev, userMsg, emptyAssistant]);
    setSubmitting(true);
    setStreamingId(assistantId);
    startTimeRef.current = Date.now();

    const controller = new AbortController();
    abortRef.current = controller;

    try {
      await streamChat({
        message: text,
        conversationId,
        signal: controller.signal,

        onStep: (step: AgentStep) => {
          setMessages((prev) =>
            prev.map((m) => {
              if (m.id !== assistantId) return m;
              const existing = m.steps || [];
              // Mark any in_progress as completed
              const withCompleted = existing.map((s) =>
                s.status === "in_progress" ? { ...s, status: "completed" as const } : s
              );
              // If a step with the same name already exists, replace it; otherwise append
              const alreadyExists = withCompleted.some((s) => s.step === step.step);
              const nextSteps = alreadyExists
                ? withCompleted.map((s) => (s.step === step.step ? step : s))
                : [...withCompleted, step];
              return { ...m, steps: nextSteps };
            })
          );
          scrollToBottom();
        },

        onToken: (token: string) => {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantId ? { ...m, content: m.content + token } : m
            )
          );
          scrollToBottom();
        },

        onCitation: (citation: ChatCitationItem) => {
          setMessages((prev) =>
            prev.map((m) => {
              if (m.id !== assistantId) return m;
              const existing = m.citations || [];
              // De-duplicate by chunk_id
              if (existing.some((c) => c.chunk_id === citation.chunk_id)) return m;
              return { ...m, citations: [...existing, citation] };
            })
          );
        },

        onCompleted: (result) => {
          const elapsed = (Date.now() - startTimeRef.current) / 1000;
          setMessages((prev) =>
            prev.map((m) => {
              if (m.id !== assistantId) return m;
              // Mark all steps completed
              const finalSteps = (m.steps || []).map((s) => ({
                ...s,
                status: "completed" as const,
              }));
              // Merge citations from completed event if available
              const completedCits = result.citations || m.citations || [];
              const deduped = Array.from(
                new Map(completedCits.map((c) => [c.chunk_id, c])).values()
              );
              return {
                ...m,
                grounded: result.grounded ?? m.grounded,
                abstained: result.abstained ?? false,
                citations: deduped,
                steps: finalSteps,
                durationSeconds: elapsed,
              };
            })
          );
          setSubmitting(false);
          setStreamingId(null);
        },

        onError: (err: Error) => {
          if (err.name === "AbortError" || controller.signal.aborted) return;
          setError(err.message || "Error contacting RAG service");
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantId
                ? {
                    ...m,
                    content: m.content ||
                      "I encountered a temporary service issue while processing your question. Please try again.",
                    abstained: true,
                  }
                : m
            )
          );
          setSubmitting(false);
          setStreamingId(null);
        },
      });
    } catch (err: unknown) {
      if (controller.signal.aborted) return;
      const msg = err instanceof Error ? err.message : "Error contacting RAG service";
      setError(msg);
      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantId
            ? {
                ...m,
                content: m.content ||
                  "I encountered a temporary service issue while processing your question. Please verify your connection or try again.",
                abstained: true,
              }
            : m
        )
      );
      setSubmitting(false);
      setStreamingId(null);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleSelectCitation = (citation: ChatCitationItem) => {
    setSelectedCitation(citation);
    setIsDrawerOpen(true);
  };

  const sampleQuestions = [
    "What factors most strongly predict undergraduate student retention and performance?",
    "Compare primary education enrollment and literacy trends across OECD countries.",
    "Summarize key methodologies and benchmarks used in multimodal language learning research.",
  ];

  return (
    <div className="flex flex-col h-full bg-background relative">
      {/* Scrollable Messages Container */}
      <div className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-4 max-w-4xl mx-auto w-full">
        {messages.map((m) => (
          <MessageBubble
            key={m.id}
            role={m.role}
            content={m.content}
            grounded={m.grounded}
            abstained={m.abstained}
            citations={m.citations}
            steps={m.steps}
            durationSeconds={m.durationSeconds}
            isStreaming={m.id === streamingId}
            onSelectCitation={handleSelectCitation}
          />
        ))}

        <div ref={messagesEndRef} />
      </div>

      {/* Suggested prompts if only 1 message */}
      {messages.length === 1 && !submitting && (
        <div className="max-w-4xl mx-auto w-full px-6 pb-2">
          <div className="text-xs text-muted-foreground mb-2 flex items-center gap-1.5 font-medium">
            <Sparkles className="h-3.5 w-3.5 text-primary" /> Suggested Research Queries:
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
            {sampleQuestions.map((q) => (
              <button
                key={q}
                onClick={() => handleSend(q)}
                className="text-left p-2.5 rounded-lg border border-border bg-card hover:bg-accent/40 text-xs text-foreground/90 font-medium hover:text-foreground transition-colors shadow-sm"
              >
                {q}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Error alert banner */}
      {error && (
        <div className="max-w-4xl mx-auto w-full px-6 py-1">
          <div className="flex items-center gap-2 p-2.5 rounded-md bg-destructive/10 border border-destructive/20 text-xs text-destructive">
            <AlertCircle className="h-4 w-4 shrink-0" />
            <span className="flex-1">{error}</span>
          </div>
        </div>
      )}

      {/* Input Form Bar */}
      <div className="border-t border-border bg-card/60 backdrop-blur p-4">
        <div className="max-w-4xl mx-auto w-full flex items-end gap-2">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask a question over the research corpus (e.g. student performance, STEM enrollment, OECD metrics)..."
            rows={2}
            disabled={submitting}
            className="flex-1 resize-none rounded-lg border border-input bg-card p-3 text-sm text-foreground placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-60"
          />
          {submitting ? (
            <Button
              onClick={handleStop}
              variant="outline"
              className="h-11 px-4 gap-1.5 text-destructive hover:bg-destructive/10 border-destructive/40"
            >
              <Square className="h-4 w-4 fill-current" />
              <span className="hidden sm:inline">Stop</span>
            </Button>
          ) : (
            <Button
              onClick={() => handleSend()}
              disabled={!input.trim()}
              className="h-11 px-4 gap-1.5"
            >
              <Send className="h-4 w-4" />
              <span className="hidden sm:inline">Send</span>
            </Button>
          )}
        </div>
      </div>

      {/* Evidence Drawer */}
      <EvidenceDrawer
        isOpen={isDrawerOpen}
        onClose={() => setIsDrawerOpen(false)}
        chunkId={selectedCitation?.chunk_id ?? null}
        documentId={selectedCitation?.document_id}
        citationLabel={selectedCitation?.citation_label}
        evidenceText={selectedCitation?.evidence_text}
        page={selectedCitation?.page}
      />
    </div>
  );
}
