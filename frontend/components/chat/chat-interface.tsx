"use client";

import * as React from "react";
import { Send, Sparkles, AlertCircle, Square, History, Plus, ArrowDown } from "lucide-react";
import { MessageBubble } from "@/components/chat/message-bubble";
import { ChatHistorySidebar } from "@/components/chat/chat-history-sidebar";
import { EvidenceDrawer } from "@/components/citations/evidence-drawer";
import { Button } from "@/components/ui/button";
import { streamChat, conversationsApi } from "@/lib/api";
import { getToken } from "@/lib/auth";
import { AgentStep, ChatCitationItem } from "@/lib/types";
import { validatePrompt } from "@/lib/guardrails";
import {
  StoredSession,
  getStoredSessions,
  saveStoredSession,
  deleteStoredSession,
  createNewSession,
  updateSessionMessages,
} from "@/lib/chat-storage";

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

export function ChatInterface({ conversationId: propConversationId }: ChatInterfaceProps) {
  const [sessions, setSessions] = React.useState<StoredSession[]>([]);
  const [activeSessionId, setActiveSessionId] = React.useState<string | null>(null);
  const [isSidebarOpen, setIsSidebarOpen] = React.useState(true);

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

  // Streaming live state
  const [streamingId, setStreamingId] = React.useState<string | null>(null);
  const abortRef = React.useRef<AbortController | null>(null);
  const startTimeRef = React.useRef<number>(0);

  // Evidence Inspector Modal state
  const [selectedCitation, setSelectedCitation] = React.useState<ChatCitationItem | null>(null);
  const [isDrawerOpen, setIsDrawerOpen] = React.useState(false);

  const messagesEndRef = React.useRef<HTMLDivElement>(null);
  const containerRef = React.useRef<HTMLDivElement>(null);
  const isNearBottomRef = React.useRef(true);
  const [showScrollBottom, setShowScrollBottom] = React.useState(false);

  const scrollToBottom = (behavior: ScrollBehavior = "smooth") => {
    messagesEndRef.current?.scrollIntoView({ behavior });
  };

  const handleScroll = () => {
    if (!containerRef.current) return;
    const { scrollTop, scrollHeight, clientHeight } = containerRef.current;
    const isNear = scrollHeight - scrollTop - clientHeight < 140;
    isNearBottomRef.current = isNear;
    setShowScrollBottom(!isNear && messages.length > 2);
  };

  React.useEffect(() => {
    if (isNearBottomRef.current) {
      scrollToBottom();
    }
  }, [messages, submitting]);

  // Load chat memory from localStorage and backend
  React.useEffect(() => {
    const local = getStoredSessions();
    if (local.length > 0) {
      setSessions(local);
      const target = propConversationId
        ? local.find((s) => s.id === propConversationId) || local[0]
        : local[0];
      setActiveSessionId(target.id);
      setMessages(target.messages);
    } else {
      const initial = createNewSession();
      setSessions([initial]);
      setActiveSessionId(initial.id);
      setMessages(initial.messages);
    }

    // Attempt backend sync
    conversationsApi
      .list()
      .then((backendConvs) => {
        if (!backendConvs || backendConvs.length === 0) return;
        setSessions((prev) => {
          const map = new Map(prev.map((s) => [s.id, s]));
          backendConvs.forEach((bc) => {
            if (!map.has(bc.id)) {
              map.set(bc.id, {
                id: bc.id,
                title: bc.title || "Research Conversation",
                createdAt: new Date(bc.created_at).getTime(),
                updatedAt: new Date(bc.updated_at).getTime(),
                messages: [
                  {
                    id: "initial",
                    role: "assistant",
                    content: `Session: ${bc.title || "Research Conversation"}`,
                  },
                ],
              });
            }
          });
          return Array.from(map.values()).sort((a, b) => b.updatedAt - a.updatedAt);
        });
      })
      .catch(() => {});
  }, [propConversationId]);

  // Auto-sync messages to active session in localStorage.
  // Skipped during streaming to avoid firing setSessions 10-20x/sec
  // (each setSessions re-render would retrigger this effect → infinite loop).
  React.useEffect(() => {
    if (!activeSessionId) return;
    if (streamingId) return; // defer sync until stream completes
    if (messages.length > 1 || (messages.length === 1 && messages[0].content !== "")) {
      const updated = updateSessionMessages(activeSessionId, messages);
      setSessions((prev) =>
        prev.map((s) => (s.id === updated.id ? updated : s)).sort((a, b) => b.updatedAt - a.updatedAt)
      );
    }
  }, [messages, activeSessionId, streamingId]);

  const handleNewChat = () => {
    if (submitting) {
      abortRef.current?.abort();
      setSubmitting(false);
      setStreamingId(null);
    }
    const newSession = createNewSession();
    setSessions((prev) => [newSession, ...prev]);
    setActiveSessionId(newSession.id);
    setMessages(newSession.messages);
    setError(null);
    setInput("");
  };

  const handleSelectSession = async (session: StoredSession) => {
    if (submitting) {
      abortRef.current?.abort();
      setSubmitting(false);
      setStreamingId(null);
    }
    setActiveSessionId(session.id);
    setError(null);

    // If session only contains placeholder and exists on backend, load real message history
    if (
      session.messages.length <= 1 &&
      session.messages[0]?.id === "initial" &&
      getToken()
    ) {
      try {
        const detail = await conversationsApi.get(session.id);
        if (detail && detail.messages && detail.messages.length > 0) {
          const loadedMsgs: MessageItem[] = detail.messages.map((m) => ({
            id: m.id,
            role: m.role as "user" | "assistant",
            content: m.content,
            grounded: m.grounded ?? undefined,
            abstained: m.abstained,
            citations: m.citations?.map((c) => ({
              chunk_id: c.chunk_id || "",
              document_id: null,
              citation_label: c.citation_label || null,
              page: null,
              evidence_text: null,
            })),
          }));
          setMessages(loadedMsgs);
          updateSessionMessages(session.id, loadedMsgs, detail.title || session.title);
          return;
        }
      } catch {
        // Fallback to local session messages
      }
    }

    setMessages(session.messages);
  };

  const handleDeleteSession = (id: string) => {
    deleteStoredSession(id);
    const remaining = sessions.filter((s) => s.id !== id);
    setSessions(remaining);
    if (activeSessionId === id) {
      if (remaining.length > 0) {
        setActiveSessionId(remaining[0].id);
        setMessages(remaining[0].messages);
      } else {
        const fresh = createNewSession();
        setSessions([fresh]);
        setActiveSessionId(fresh.id);
        setMessages(fresh.messages);
      }
    }
  };

  const handleStop = () => {
    abortRef.current?.abort();
    setSubmitting(false);
    setStreamingId(null);
  };

  const handleSend = async (textToSend?: string) => {
    const text = (textToSend || input).trim();
    if (!text || submitting) return;

    // Client-side Input Guardrail
    const guardCheck = validatePrompt(text);
    if (!guardCheck.safe) {
      setError(
        guardCheck.error ||
          "Input blocked by security guardrails: prohibited keywords or jailbreak detected."
      );
      return;
    }

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

    // Snapshot the conversation history BEFORE appending the current message
    // so the backend can resolve "continue", pronouns, and follow-ups
    const historySnapshot = messages
      .filter((m) => m.content && m.content.trim().length > 0)
      .slice(-10)
      .map((m) => ({ role: m.role, content: m.content.trim() }));

    const nextMessages = [...messages, userMsg, emptyAssistant];
    setMessages(nextMessages);
    setSubmitting(true);
    setStreamingId(assistantId);
    startTimeRef.current = Date.now();

    const controller = new AbortController();
    abortRef.current = controller;

    try {
      await streamChat({
        message: text,
        conversationId: activeSessionId || undefined,
        history: historySnapshot.length > 0 ? historySnapshot : undefined,
        signal: controller.signal,

        onStep: (step: AgentStep) => {
          setMessages((prev) =>
            prev.map((m) => {
              if (m.id !== assistantId) return m;
              const existing = m.steps || [];
              const withCompleted = existing.map((s) =>
                s.status === "in_progress" ? { ...s, status: "completed" as const } : s
              );
              const alreadyExists = withCompleted.some((s) => s.step === step.step);
              const nextSteps = alreadyExists
                ? withCompleted.map((s) => (s.step === step.step ? step : s))
                : [...withCompleted, step];
              return { ...m, steps: nextSteps };
            })
          );
          // scrollToBottom is handled by the useEffect([messages]) watcher above
        },

        onToken: (token: string) => {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantId ? { ...m, content: m.content + token } : m
            )
          );
          // scrollToBottom is handled by the useEffect([messages]) watcher above
        },

        onCitation: (citation: ChatCitationItem) => {
          setMessages((prev) =>
            prev.map((m) => {
              if (m.id !== assistantId) return m;
              const existing = m.citations || [];
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
              const finalSteps = (m.steps || []).map((s) => ({
                ...s,
                status: "completed" as const,
              }));
              const completedCits = result.citations || m.citations || [];
              const deduped = Array.from(
                new Map(completedCits.map((c) => [c.chunk_id, c])).values()
              );
              return {
                ...m,
                id: result.messageId || m.id,
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
          const isSecurity =
            err.message.includes("guardrail") ||
            err.message.includes("blocked") ||
            err.message.includes("prohibited");
          setError(err.message || "Error contacting RAG service");
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantId
                ? {
                    ...m,
                    content: isSecurity
                      ? err.message
                      : m.content ||
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
      const isSecurity =
        msg.includes("guardrail") ||
        msg.includes("blocked") ||
        msg.includes("prohibited");
      setError(msg);
      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantId
            ? {
                ...m,
                content: isSecurity
                  ? msg
                  : m.content ||
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
    if (citation.chunk_id) {
      conversationsApi
        .trackCitationClick({
          chunk_id: citation.chunk_id,
          conversation_id: activeSessionId || undefined,
          document_title: citation.document_title || undefined,
        })
        .catch(() => {});
    }
  };

  const sampleQuestions = [
    "What factors most strongly predict undergraduate student retention and performance?",
    "Compare primary education enrollment and literacy trends across OECD countries.",
    "Summarize key methodologies and benchmarks used in multimodal language learning research.",
  ];

  return (
    <div className="flex h-full w-full bg-background relative overflow-hidden">
      {/* Chat Memory Sidebar */}
      <ChatHistorySidebar
        sessions={sessions}
        activeSessionId={activeSessionId}
        onSelectSession={handleSelectSession}
        onNewChat={handleNewChat}
        onDeleteSession={handleDeleteSession}
        isOpen={isSidebarOpen}
        onToggle={() => setIsSidebarOpen(!isSidebarOpen)}
      />

      {/* Main Chat Center Container */}
      <div className="flex-1 flex flex-col min-w-0 h-full relative">
        {/* Top Chat Bar */}
        <div className="h-11 px-4 border-b border-border/70 flex items-center justify-between bg-card/40 backdrop-blur shrink-0">
          <div className="flex items-center gap-2 min-w-0">
            <button
              onClick={() => setIsSidebarOpen(!isSidebarOpen)}
              className="p-1 rounded-md text-muted-foreground hover:text-foreground hover:bg-accent transition-colors flex items-center gap-1.5 text-xs"
              title="Toggle Chat Memory"
            >
              <History className="h-3.5 w-3.5" />
              <span className="hidden sm:inline font-medium">Memory</span>
            </button>
            <span className="text-border">|</span>
            <span className="text-xs font-semibold text-foreground truncate max-w-[260px] sm:max-w-md">
              {sessions.find((s) => s.id === activeSessionId)?.title || "Research Assistant"}
            </span>
          </div>

          <Button
            size="sm"
            variant="ghost"
            onClick={handleNewChat}
            className="h-7 text-xs px-2 gap-1 text-muted-foreground hover:text-foreground"
          >
            <Plus className="h-3 w-3" />
            <span className="hidden sm:inline">New Session</span>
          </Button>
        </div>

        {/* Scrollable Messages Container */}
        <div
          ref={containerRef}
          onScroll={handleScroll}
          className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-4 max-w-4xl mx-auto w-full relative"
        >
          {messages.map((m, idx) => {
            const precedingUserMsg = messages
              .slice(0, idx)
              .reverse()
              .find((prev) => prev.role === "user");

            return (
              <MessageBubble
                key={m.id}
                id={m.id}
                conversationId={activeSessionId || undefined}
                role={m.role}
                content={m.content}
                grounded={m.grounded}
                abstained={m.abstained}
                citations={m.citations}
                steps={m.steps}
                durationSeconds={m.durationSeconds}
                isStreaming={m.id === streamingId}
                userQuery={precedingUserMsg?.content}
                onSelectCitation={handleSelectCitation}
              />
            );
          })}

          <div ref={messagesEndRef} />
        </div>

        {/* Floating Scroll to Bottom Button */}
        {showScrollBottom && (
          <div className="max-w-4xl mx-auto w-full relative flex justify-end px-6 pointer-events-none">
            <button
              type="button"
              onClick={() => scrollToBottom("smooth")}
              className="pointer-events-auto -mt-12 mb-2 z-20 flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-card/95 border border-border shadow-lg text-xs font-medium text-foreground hover:bg-accent hover:border-primary/50 transition-all backdrop-blur animate-in fade-in slide-in-from-bottom-2"
            >
              <ArrowDown className="h-3.5 w-3.5 text-primary animate-bounce" />
              <span>Latest messages</span>
            </button>
          </div>
        )}

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
                  className="text-left p-2.5 rounded-lg border border-border bg-card hover:bg-accent/40 text-xs text-foreground/90 font-medium hover:text-foreground transition-colors shadow-xs"
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
        <div className="border-t border-border bg-card/60 backdrop-blur p-4 relative">
          {submitting && (
            <div className="absolute top-0 left-0 right-0 h-[2px] bg-primary/20 overflow-hidden">
              <div className="h-full w-1/3 bg-primary animate-pulse" />
            </div>
          )}
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
                className="h-11 px-4 gap-2 text-destructive border-destructive/40 hover:bg-destructive/10 relative overflow-hidden transition-all shadow-xs"
              >
                <span className="relative flex h-2 w-2">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-destructive opacity-75" />
                  <span className="relative inline-flex rounded-full h-2 w-2 bg-destructive" />
                </span>
                <Square className="h-3.5 w-3.5 fill-current" />
                <span className="hidden sm:inline font-medium">Stop</span>
              </Button>
            ) : (
              <Button
                onClick={() => handleSend()}
                disabled={!input.trim()}
                className="h-11 px-4 gap-1.5 shadow-sm"
              >
                <Send className="h-4 w-4" />
                <span className="hidden sm:inline">Send</span>
              </Button>
            )}
          </div>
        </div>
      </div>

      {/* Split-Screen Evidence Inspector Modal (Matches Screenshot) */}
      <EvidenceDrawer
        isOpen={isDrawerOpen}
        onClose={() => setIsDrawerOpen(false)}
        chunkId={selectedCitation?.chunk_id ?? null}
        documentId={selectedCitation?.document_id}
        documentTitle={selectedCitation?.document_title}
        citationLabel={selectedCitation?.citation_label}
        evidenceText={selectedCitation?.evidence_text}
        page={selectedCitation?.page}
        rank={1}
        totalCandidates={6}
      />
    </div>
  );
}
