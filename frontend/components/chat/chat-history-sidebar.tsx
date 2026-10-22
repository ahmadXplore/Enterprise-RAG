"use client";

import * as React from "react";
import {
  Plus,
  MessageSquare,
  Trash2,
  Search,
  Clock,
  ChevronLeft,
  ChevronRight,
  Sparkles,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { StoredSession, deleteStoredSession } from "@/lib/chat-storage";

export interface ChatHistorySidebarProps {
  sessions: StoredSession[];
  activeSessionId: string | null;
  onSelectSession: (session: StoredSession) => void;
  onNewChat: () => void;
  onDeleteSession: (id: string) => void;
  isOpen: boolean;
  onToggle: () => void;
}

function formatRelativeTime(timestamp: number): string {
  const diff = Date.now() - timestamp;
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "Just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days === 1) return "Yesterday";
  if (days < 7) return `${days}d ago`;
  return new Date(timestamp).toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
  });
}

export function ChatHistorySidebar({
  sessions,
  activeSessionId,
  onSelectSession,
  onNewChat,
  onDeleteSession,
  isOpen,
  onToggle,
}: ChatHistorySidebarProps) {
  const [searchQuery, setSearchQuery] = React.useState("");

  const filteredSessions = React.useMemo(() => {
    if (!searchQuery.trim()) return sessions;
    const q = searchQuery.toLowerCase();
    return sessions.filter(
      (s) =>
        s.title.toLowerCase().includes(q) ||
        s.messages.some((m) => m.content.toLowerCase().includes(q))
    );
  }, [sessions, searchQuery]);

  // Group by Today, Last 7 Days, Older
  const grouped = React.useMemo(() => {
    const today: StoredSession[] = [];
    const thisWeek: StoredSession[] = [];
    const older: StoredSession[] = [];

    const now = Date.now();
    const oneDay = 24 * 60 * 60 * 1000;
    const sevenDays = 7 * oneDay;

    filteredSessions.forEach((s) => {
      const age = now - s.updatedAt;
      if (age < oneDay) {
        today.push(s);
      } else if (age < sevenDays) {
        thisWeek.push(s);
      } else {
        older.push(s);
      }
    });

    return { today, thisWeek, older };
  }, [filteredSessions]);

  if (!isOpen) {
    return (
      <button
        onClick={onToggle}
        className="hidden md:flex flex-col items-center py-4 px-2 bg-card/60 hover:bg-card border-r border-border transition-colors text-muted-foreground hover:text-foreground h-full"
        title="Open Chat Memory"
        aria-label="Open Chat Memory"
      >
        <ChevronRight className="h-4 w-4 mb-3" />
        <span className="[writing-mode:vertical-rl] text-xs font-semibold tracking-wider uppercase text-muted-foreground/80 flex items-center gap-1.5 py-1">
          <Clock className="h-3 w-3 inline rotate-90" /> Chat Memory ({sessions.length})
        </span>
      </button>
    );
  }

  return (
    <aside className="w-72 sm:w-80 h-full bg-card/95 border-r border-border flex flex-col shrink-0 z-20 backdrop-blur transition-all duration-200">
      {/* Top Header */}
      <div className="p-3.5 border-b border-border space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="h-7 w-7 rounded-md bg-primary/10 border border-primary/20 flex items-center justify-center text-primary">
              <Clock className="h-4 w-4" />
            </div>
            <div>
              <h2 className="text-sm font-bold text-foreground">Chat Memory</h2>
              <p className="text-[11px] text-muted-foreground">Previous research sessions</p>
            </div>
          </div>
          <div className="flex items-center gap-1">
            <Button
              size="sm"
              onClick={onNewChat}
              className="h-8 text-xs font-medium gap-1.5 shadow-sm"
            >
              <Plus className="h-3.5 w-3.5" />
              <span>New Chat</span>
            </Button>
            <button
              onClick={onToggle}
              className="p-1.5 rounded-md text-muted-foreground hover:text-foreground hover:bg-accent transition-colors"
              title="Collapse sidebar"
              aria-label="Collapse sidebar"
            >
              <ChevronLeft className="h-4 w-4" />
            </button>
          </div>
        </div>

        {/* Filter Input */}
        <div className="relative">
          <Search className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-muted-foreground" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search past conversations..."
            className="w-full pl-8 pr-3 py-1.5 rounded-md border border-input bg-background text-xs placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
          />
        </div>
      </div>

      {/* Sessions List */}
      <div className="flex-1 overflow-y-auto p-2 space-y-4">
        {filteredSessions.length === 0 ? (
          <div className="py-12 px-4 text-center space-y-2">
            <MessageSquare className="h-8 w-8 mx-auto text-muted-foreground/40" />
            <p className="text-xs text-muted-foreground font-medium">
              {searchQuery ? "No matching chats found." : "No saved chats yet."}
            </p>
            <p className="text-[11px] text-muted-foreground/70">
              {searchQuery
                ? "Try a different search term"
                : "Ask a question to start your first session"}
            </p>
          </div>
        ) : (
          <>
            {grouped.today.length > 0 && (
              <div className="space-y-1">
                <div className="px-2.5 py-1 text-[10px] font-semibold tracking-wider uppercase text-muted-foreground">
                  Today
                </div>
                {grouped.today.map((s) => (
                  <SessionItem
                    key={s.id}
                    session={s}
                    isActive={s.id === activeSessionId}
                    onSelect={() => onSelectSession(s)}
                    onDelete={(e) => {
                      e.stopPropagation();
                      onDeleteSession(s.id);
                    }}
                  />
                ))}
              </div>
            )}

            {grouped.thisWeek.length > 0 && (
              <div className="space-y-1">
                <div className="px-2.5 py-1 text-[10px] font-semibold tracking-wider uppercase text-muted-foreground">
                  Previous 7 Days
                </div>
                {grouped.thisWeek.map((s) => (
                  <SessionItem
                    key={s.id}
                    session={s}
                    isActive={s.id === activeSessionId}
                    onSelect={() => onSelectSession(s)}
                    onDelete={(e) => {
                      e.stopPropagation();
                      onDeleteSession(s.id);
                    }}
                  />
                ))}
              </div>
            )}

            {grouped.older.length > 0 && (
              <div className="space-y-1">
                <div className="px-2.5 py-1 text-[10px] font-semibold tracking-wider uppercase text-muted-foreground">
                  Older
                </div>
                {grouped.older.map((s) => (
                  <SessionItem
                    key={s.id}
                    session={s}
                    isActive={s.id === activeSessionId}
                    onSelect={() => onSelectSession(s)}
                    onDelete={(e) => {
                      e.stopPropagation();
                      onDeleteSession(s.id);
                    }}
                  />
                ))}
              </div>
            )}
          </>
        )}
      </div>

      {/* Footer Info */}
      <div className="p-3 border-t border-border bg-card/60 flex items-center justify-between text-[11px] text-muted-foreground">
        <span className="flex items-center gap-1">
          <Sparkles className="h-3 w-3 text-primary" /> Stored locally & DB synced
        </span>
        <span className="font-mono text-[10px]">{sessions.length} sessions</span>
      </div>
    </aside>
  );
}

function SessionItem({
  session,
  isActive,
  onSelect,
  onDelete,
}: {
  session: StoredSession;
  isActive: boolean;
  onSelect: () => void;
  onDelete: (e: React.MouseEvent) => void;
}) {
  return (
    <div
      onClick={onSelect}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onSelect();
        }
      }}
      className={`group relative flex items-center justify-between gap-2 px-3 py-2.5 rounded-lg cursor-pointer transition-colors text-left ${
        isActive
          ? "bg-primary/15 border border-primary/30 text-foreground font-medium"
          : "hover:bg-accent/50 text-foreground/80 hover:text-foreground border border-transparent"
      }`}
    >
      <div className="flex items-start gap-2.5 min-w-0 flex-1">
        <MessageSquare
          className={`h-4 w-4 shrink-0 mt-0.5 ${
            isActive ? "text-primary" : "text-muted-foreground group-hover:text-foreground"
          }`}
        />
        <div className="min-w-0 flex-1">
          <div className="text-xs truncate font-medium leading-snug">{session.title}</div>
          <div className="text-[10px] text-muted-foreground font-mono mt-0.5">
            {formatRelativeTime(session.updatedAt)} • {session.messages.length} msgs
          </div>
        </div>
      </div>

      <button
        onClick={onDelete}
        title="Delete chat session"
        aria-label="Delete chat session"
        className="opacity-0 group-hover:opacity-100 p-1 rounded hover:bg-destructive/15 hover:text-destructive text-muted-foreground transition-all shrink-0"
      >
        <Trash2 className="h-3.5 w-3.5" />
      </button>
    </div>
  );
}
