"use client";

import * as React from "react";
import {
  Card,
  CardHeader,
  CardTitle,
  CardContent,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  MessageSquare,
  AlertTriangle,
  Flame,
  Search,
  Clock,
  Shield,
  User,
  ArrowRight,
  TrendingUp,
} from "lucide-react";
import {
  LongestConversationItem,
  FrustrationIncidentItem,
  UserCorrectionItem,
  IdkIncidentItem,
} from "@/lib/api";
import { ThumbsDown, MessageSquareQuote, FileQuestion } from "lucide-react";

interface RealUserConversationsMonitorProps {
  longestConversations: LongestConversationItem[];
  frustrationIncidents: FrustrationIncidentItem[];
  userCorrections?: UserCorrectionItem[];
  idkIncidents?: IdkIncidentItem[];
  idkRate?: number;
  satisfactionRate?: number;
}

export function RealUserConversationsMonitor({
  longestConversations = [],
  frustrationIncidents = [],
  userCorrections = [],
  idkIncidents = [],
  idkRate = 0,
  satisfactionRate = 100,
}: RealUserConversationsMonitorProps) {
  const [activeTab, setActiveTab] = React.useState<"longest" | "frustration" | "corrections" | "idk_triggers">(
    "longest"
  );
  const [searchTerm, setSearchTerm] = React.useState("");

  const filteredLongest = React.useMemo(() => {
    if (!searchTerm) return longestConversations;
    const term = searchTerm.toLowerCase();
    return longestConversations.filter(
      (c) =>
        c.title.toLowerCase().includes(term) ||
        c.anonymized_user.toLowerCase().includes(term) ||
        c.first_query.toLowerCase().includes(term) ||
        c.last_query.toLowerCase().includes(term)
    );
  }, [longestConversations, searchTerm]);

  const filteredFrustration = React.useMemo(() => {
    if (!searchTerm) return frustrationIncidents;
    const term = searchTerm.toLowerCase();
    return frustrationIncidents.filter(
      (f) =>
        f.matched_signal.toLowerCase().includes(term) ||
        f.message_snippet.toLowerCase().includes(term) ||
        f.anonymized_user.toLowerCase().includes(term)
    );
  }, [frustrationIncidents, searchTerm]);

  const filteredCorrections = React.useMemo(() => {
    if (!searchTerm) return userCorrections;
    const term = searchTerm.toLowerCase();
    return userCorrections.filter(
      (c) =>
        c.correction_text.toLowerCase().includes(term) ||
        c.user_query.toLowerCase().includes(term) ||
        c.anonymized_user.toLowerCase().includes(term) ||
        (c.tags && c.tags.some((t) => t.toLowerCase().includes(term)))
    );
  }, [userCorrections, searchTerm]);

  const filteredIdk = React.useMemo(() => {
    if (!searchTerm) return idkIncidents;
    const term = searchTerm.toLowerCase();
    return idkIncidents.filter(
      (i) =>
        i.user_query.toLowerCase().includes(term) ||
        i.assistant_snippet.toLowerCase().includes(term) ||
        i.anonymized_user.toLowerCase().includes(term)
    );
  }, [idkIncidents, searchTerm]);

  const strugglingCount = longestConversations.filter(
    (c) => c.is_struggling || c.total_turns >= 10
  ).length;

  return (
    <Card className="border-border bg-card shadow-xs">
      <CardHeader className="pb-3 border-b border-border">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <CardTitle className="text-sm font-semibold flex items-center gap-2 text-foreground">
              <MessageSquare className="h-4 w-4 text-primary" />
              <span>Monitor Real User Conversations (Anonymized Logging)</span>
            </CardTitle>
            <p className="text-xs text-muted-foreground mt-0.5">
              Review actual user sessions to diagnose hallucinations, context loss, and user friction.
            </p>
          </div>

          <div className="flex items-center gap-2">
            <div className="relative">
              <Search className="h-3.5 w-3.5 absolute left-2.5 top-1/2 -translate-y-1/2 text-muted-foreground" />
              <input
                type="text"
                placeholder="Search session logs..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="h-8 pl-8 pr-3 text-xs rounded-md border border-border bg-muted/40 focus:bg-background focus:outline-none focus:ring-1 focus:ring-primary w-40 sm:w-56"
              />
            </div>
          </div>
        </div>

        {/* Tab Selection Navigation */}
        <div className="flex items-center gap-2 pt-3">
          <button
            type="button"
            onClick={() => setActiveTab("longest")}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
              activeTab === "longest"
                ? "bg-primary text-primary-foreground shadow-xs"
                : "bg-muted/60 text-muted-foreground hover:text-foreground hover:bg-muted"
            }`}
          >
            <Clock className="h-3.5 w-3.5" />
            <span>Longest Conversations (10+ turns)</span>
            {strugglingCount > 0 && (
              <span className="ml-1 px-1.5 py-0.2 rounded-full text-[10px] bg-amber-500/20 text-amber-900 dark:text-amber-200 font-mono font-bold">
                {strugglingCount}
              </span>
            )}
          </button>

          <button
            type="button"
            onClick={() => setActiveTab("frustration")}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
              activeTab === "frustration"
                ? "bg-primary text-primary-foreground shadow-xs"
                : "bg-muted/60 text-muted-foreground hover:text-foreground hover:bg-muted"
            }`}
          >
            <Flame className="h-3.5 w-3.5 text-amber-500" />
            <span>Implicit Frustration Signals</span>
            {frustrationIncidents.length > 0 && (
              <span className="ml-1 px-1.5 py-0.2 rounded-full text-[10px] bg-red-500/20 text-red-900 dark:text-red-200 font-mono font-bold">
                {frustrationIncidents.length}
              </span>
            )}
          </button>

          <button
            type="button"
            onClick={() => setActiveTab("corrections")}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
              activeTab === "corrections"
                ? "bg-primary text-primary-foreground shadow-xs"
                : "bg-muted/60 text-muted-foreground hover:text-foreground hover:bg-muted"
            }`}
          >
            <ThumbsDown className="h-3.5 w-3.5 text-rose-500" />
            <span>User Corrections (&ldquo;What was missing?&rdquo;)</span>
            {userCorrections.length > 0 && (
              <span className="ml-1 px-1.5 py-0.2 rounded-full text-[10px] bg-rose-500/20 text-rose-900 dark:text-rose-200 font-mono font-bold">
                {userCorrections.length}
              </span>
            )}
          </button>

          <button
            type="button"
            onClick={() => setActiveTab("idk_triggers")}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
              activeTab === "idk_triggers"
                ? "bg-primary text-primary-foreground shadow-xs"
                : "bg-muted/60 text-muted-foreground hover:text-foreground hover:bg-muted"
            }`}
          >
            <FileQuestion className="h-3.5 w-3.5 text-amber-500" />
            <span>&ldquo;I Don&apos;t Know&rdquo; Triggers</span>
            {idkIncidents.length > 0 && (
              <span className="ml-1 px-1.5 py-0.2 rounded-full text-[10px] bg-amber-500/20 text-amber-900 dark:text-amber-200 font-mono font-bold">
                {idkIncidents.length}
              </span>
            )}
          </button>
        </div>
      </CardHeader>

      <CardContent className="p-0">
        {activeTab === "longest" && (
          <div className="divide-y divide-border/60">
            <div className="p-3 bg-muted/30 text-[11px] text-muted-foreground flex items-center gap-2 border-b border-border/50">
              <TrendingUp className="h-3.5 w-3.5 text-amber-500 shrink-0" />
              <span>
                <strong>Heuristic:</strong> Users chatting for 10+ turns are often struggling to obtain a complete answer due to hallucination loops or missing retrieval context.
              </span>
            </div>

            {filteredLongest.length === 0 ? (
              <div className="py-12 text-center text-xs text-muted-foreground">
                No conversations matching this criteria have been recorded yet.
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-xs text-left border-collapse">
                  <thead>
                    <tr className="border-b border-border bg-muted/40 text-muted-foreground font-semibold">
                      <th className="py-2.5 px-4">Anonymized User</th>
                      <th className="py-2.5 px-4">Session Topic</th>
                      <th className="py-2.5 px-4 text-center">Turn Count</th>
                      <th className="py-2.5 px-4">Initial Inquiry Preview</th>
                      <th className="py-2.5 px-4">Latest Follow-up Preview</th>
                      <th className="py-2.5 px-4 font-mono">Last Active</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border/60">
                    {filteredLongest.map((c) => {
                      const isStruggling = c.is_struggling || c.total_turns >= 10;
                      return (
                        <tr
                          key={c.conversation_id}
                          className="hover:bg-accent/40 transition-colors"
                        >
                          <td className="py-3 px-4 font-mono font-medium text-foreground whitespace-nowrap">
                            <div className="flex items-center gap-1.5">
                              <Shield className="h-3.5 w-3.5 text-primary/70" />
                              <span>{c.anonymized_user}</span>
                            </div>
                          </td>
                          <td className="py-3 px-4 font-medium text-foreground max-w-xs truncate">
                            {c.title}
                          </td>
                          <td className="py-3 px-4 text-center whitespace-nowrap">
                            {isStruggling ? (
                              <Badge
                                variant="destructive"
                                className="font-mono text-[10px] py-0 gap-1 font-bold"
                              >
                                <AlertTriangle className="h-3 w-3" />
                                {c.total_turns} Turns (Struggling)
                              </Badge>
                            ) : (
                              <Badge
                                variant="outline"
                                className="font-mono text-[10px] py-0 text-muted-foreground"
                              >
                                {c.total_turns} Turns
                              </Badge>
                            )}
                          </td>
                          <td
                            className="py-3 px-4 text-muted-foreground max-w-xs truncate"
                            title={c.first_query}
                          >
                            &ldquo;{c.first_query}&rdquo;
                          </td>
                          <td
                            className="py-3 px-4 text-foreground/90 max-w-xs truncate"
                            title={c.last_query}
                          >
                            &ldquo;{c.last_query}&rdquo;
                          </td>
                          <td className="py-3 px-4 font-mono text-muted-foreground text-[11px] whitespace-nowrap">
                            {new Date(c.last_activity).toLocaleString("en-PK", { timeZone: "Asia/Karachi", dateStyle: "short", timeStyle: "short" })}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}

        {activeTab === "frustration" && (
          <div className="divide-y divide-border/60">
            <div className="p-3 bg-muted/30 text-[11px] text-muted-foreground flex items-center gap-2 border-b border-border/50">
              <AlertTriangle className="h-3.5 w-3.5 text-red-500 shrink-0" />
              <span>
                <strong>Heuristic:</strong> Searching user logs for negative sentiment keywords (&ldquo;wrong&rdquo;, &ldquo;not what I asked&rdquo;, &ldquo;unhelpful&rdquo;) or repeated identical inquiries isolates points of failure.
              </span>
            </div>

            {filteredFrustration.length === 0 ? (
              <div className="py-12 text-center text-xs text-muted-foreground">
                Zero implicit frustration signals detected in current user sessions. Production interactions remain positive.
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-xs text-left border-collapse">
                  <thead>
                    <tr className="border-b border-border bg-muted/40 text-muted-foreground font-semibold">
                      <th className="py-2.5 px-4">Anonymized User</th>
                      <th className="py-2.5 px-4">Detected Signal</th>
                      <th className="py-2.5 px-4 text-center">Turn</th>
                      <th className="py-2.5 px-4">User Query Snippet</th>
                      <th className="py-2.5 px-4 font-mono">Timestamp</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border/60">
                    {filteredFrustration.map((f, idx) => (
                      <tr
                        key={`${f.conversation_id}-${idx}`}
                        className="hover:bg-accent/40 transition-colors"
                      >
                        <td className="py-3 px-4 font-mono font-medium text-foreground whitespace-nowrap">
                          <div className="flex items-center gap-1.5">
                            <Shield className="h-3.5 w-3.5 text-primary/70" />
                            <span>{f.anonymized_user}</span>
                          </div>
                        </td>
                        <td className="py-3 px-4 whitespace-nowrap">
                          {f.signal_type === "repeated_query" ? (
                            <Badge
                              variant="outline"
                              className="border-amber-500/40 text-amber-700 dark:text-amber-300 font-mono text-[10px] py-0"
                            >
                              Repeated Identical Prompt
                            </Badge>
                          ) : (
                            <Badge
                              variant="destructive"
                              className="font-mono text-[10px] py-0 gap-1 uppercase"
                            >
                              &ldquo;{f.matched_signal}&rdquo;
                            </Badge>
                          )}
                        </td>
                        <td className="py-3 px-4 text-center font-mono text-[11px] text-muted-foreground">
                          Turn #{f.turn_index}
                        </td>
                        <td
                          className="py-3 px-4 text-foreground/90 max-w-md truncate font-sans"
                          title={f.message_snippet}
                        >
                          &ldquo;{f.message_snippet}&rdquo;
                        </td>
                        <td className="py-3 px-4 font-mono text-muted-foreground text-[11px] whitespace-nowrap">
                          {new Date(f.timestamp).toLocaleString("en-PK", { timeZone: "Asia/Karachi", dateStyle: "short", timeStyle: "short" })}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}

        {/* Tab 3: User Corrections ("What was missing or incorrect?") */}
        {activeTab === "corrections" && (
          <div className="divide-y divide-border/60">
            <div className="p-3.5 bg-rose-500/5 text-xs text-muted-foreground flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-border/50">
              <div className="flex items-center gap-2">
                <MessageSquareQuote className="h-4 w-4 text-rose-500 shrink-0" />
                <span>
                  <strong>Real-Time Correction Pipeline:</strong> Prompted on every thumbs-down: <em>&ldquo;What was missing or incorrect?&rdquo;</em> Directly captures missing documents and factual inaccuracies.
                </span>
              </div>
              <Badge variant="outline" className="border-rose-500/30 text-rose-600 dark:text-rose-400 font-mono text-[10px] py-0 self-start sm:self-auto">
                {userCorrections.length} Gaps Captured
              </Badge>
            </div>

            {filteredCorrections.length === 0 ? (
              <div className="p-12 text-center text-xs text-muted-foreground">
                No user corrections matching the search criteria. Users haven&apos;t reported missing facts in these sessions.
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-xs text-left border-collapse">
                  <thead>
                    <tr className="border-b border-border bg-muted/40 text-muted-foreground font-semibold">
                      <th className="py-2.5 px-4 font-mono">User</th>
                      <th className="py-2.5 px-4">User Query</th>
                      <th className="py-2.5 px-4">What Was Missing or Incorrect?</th>
                      <th className="py-2.5 px-4">Gap Category</th>
                      <th className="py-2.5 px-4">Timestamp</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border/60">
                    {filteredCorrections.map((c, idx) => (
                      <tr
                        key={`${c.id}-${idx}`}
                        className="hover:bg-accent/40 transition-colors"
                      >
                        <td className="py-3 px-4 font-mono font-medium text-foreground whitespace-nowrap">
                          <div className="flex items-center gap-1.5">
                            <Shield className="h-3.5 w-3.5 text-primary/70" />
                            <span>{c.anonymized_user}</span>
                          </div>
                        </td>
                        <td
                          className="py-3 px-4 text-foreground/90 max-w-xs truncate font-sans"
                          title={c.user_query}
                        >
                          &ldquo;{c.user_query}&rdquo;
                        </td>
                        <td className="py-3 px-4 max-w-md font-sans">
                          <div className="p-2 rounded-md bg-rose-500/10 border border-rose-500/20 text-rose-950 dark:text-rose-200 leading-relaxed text-[11px]">
                            &ldquo;{c.correction_text}&rdquo;
                          </div>
                        </td>
                        <td className="py-3 px-4">
                          <div className="flex flex-wrap gap-1">
                            {c.tags && c.tags.length > 0 ? (
                              c.tags.map((t) => (
                                <Badge
                                  key={t}
                                  variant="secondary"
                                  className="text-[9px] py-0 px-1.5 font-medium"
                                >
                                  {t}
                                </Badge>
                              ))
                            ) : (
                              <Badge
                                variant="outline"
                                className="border-border text-[9px] py-0 px-1.5 text-muted-foreground"
                              >
                                General Gap
                              </Badge>
                            )}
                          </div>
                        </td>
                        <td className="py-3 px-4 font-mono text-muted-foreground text-[11px] whitespace-nowrap">
                          {new Date(c.timestamp).toLocaleString("en-PK", { timeZone: "Asia/Karachi", dateStyle: "short", timeStyle: "short" })}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}

        {/* Tab 4: "I Don't Know" Triggers Log */}
        {activeTab === "idk_triggers" && (
          <div className="divide-y divide-border/60">
            <div className="p-3.5 bg-amber-500/5 text-xs text-muted-foreground flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-border/50">
              <div className="flex items-center gap-2">
                <FileQuestion className="h-4 w-4 text-amber-500 shrink-0" />
                <span>
                  <strong>Canonical Trigger Phrase:</strong> Programmed to say <em>&ldquo;I cannot find that in the provided documentation&rdquo;</em> when evidence is missing.
                </span>
              </div>
              <div className="flex items-center gap-1.5 self-start sm:self-auto">
                <Badge variant="outline" className="border-amber-500/30 text-amber-700 dark:text-amber-300 font-mono text-[10px] py-0">
                  Trigger Rate: {idkRate}%
                </Badge>
                <Badge variant="secondary" className="font-mono text-[10px] py-0">
                  {idkIncidents.length} Occurrences
                </Badge>
              </div>
            </div>

            {filteredIdk.length === 0 ? (
              <div className="p-12 text-center text-xs text-muted-foreground">
                No &ldquo;I don&apos;t know&rdquo; triggers recorded. All queries had sufficient evidence in the vector database.
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-xs text-left border-collapse">
                  <thead>
                    <tr className="border-b border-border bg-muted/40 text-muted-foreground font-semibold">
                      <th className="py-2.5 px-4 font-mono">User</th>
                      <th className="py-2.5 px-4">User Question (Trigger)</th>
                      <th className="py-2.5 px-4">Assistant Response Snippet</th>
                      <th className="py-2.5 px-4 text-center">Status</th>
                      <th className="py-2.5 px-4">Timestamp</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border/60">
                    {filteredIdk.map((i, idx) => (
                      <tr
                        key={`${i.conversation_id}-${idx}`}
                        className="hover:bg-accent/40 transition-colors"
                      >
                        <td className="py-3 px-4 font-mono font-medium text-foreground whitespace-nowrap">
                          <div className="flex items-center gap-1.5">
                            <Shield className="h-3.5 w-3.5 text-primary/70" />
                            <span>{i.anonymized_user}</span>
                          </div>
                        </td>
                        <td
                          className="py-3 px-4 text-foreground/90 max-w-sm font-sans font-medium"
                          title={i.user_query}
                        >
                          &ldquo;{i.user_query}&rdquo;
                        </td>
                        <td
                          className="py-3 px-4 text-muted-foreground max-w-md truncate font-sans"
                          title={i.assistant_snippet}
                        >
                          {i.assistant_snippet}
                        </td>
                        <td className="py-3 px-4 text-center whitespace-nowrap">
                          <Badge
                            variant="outline"
                            className="border-amber-500/40 text-amber-700 dark:text-amber-300 font-mono text-[10px] py-0"
                          >
                            Knowledge Gap
                          </Badge>
                        </td>
                        <td className="py-3 px-4 font-mono text-muted-foreground text-[11px] whitespace-nowrap">
                          {new Date(i.timestamp).toLocaleString("en-PK", { timeZone: "Asia/Karachi", dateStyle: "short", timeStyle: "short" })}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
