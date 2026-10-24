"use client";

import * as React from "react";
import { ThumbsUp, ThumbsDown, Check, Send, Sparkles, X, MessageSquareQuote } from "lucide-react";
import { chatApi } from "@/lib/api";

export interface ResponseFeedbackProps {
  messageId: string;
  conversationId?: string;
  userQuery?: string;
  initialRating?: "thumbs_up" | "thumbs_down" | null;
  initialCorrection?: string | null;
  onFeedbackSaved?: (rating: "thumbs_up" | "thumbs_down", text?: string) => void;
}

const COMMON_GAP_TAGS = [
  "Missing relevant facts",
  "Incorrect information",
  "Outdated documentation",
  "Calculation / metric error",
  "Unrelated citations",
];

export function ResponseFeedback({
  messageId,
  conversationId,
  userQuery,
  initialRating = null,
  initialCorrection = null,
  onFeedbackSaved,
}: ResponseFeedbackProps) {
  const [rating, setRating] = React.useState<"thumbs_up" | "thumbs_down" | null>(initialRating);
  const [showCorrectionUI, setShowCorrectionUI] = React.useState(false);
  const [correctionText, setCorrectionText] = React.useState(initialCorrection || "");
  const [selectedTags, setSelectedTags] = React.useState<string[]>([]);
  const [isSubmitting, setIsSubmitting] = React.useState(false);
  const [submittedFeedback, setSubmittedFeedback] = React.useState<boolean>(Boolean(initialCorrection));
  const [toastMessage, setToastMessage] = React.useState<string | null>(null);

  // Sync if initialRating changes
  React.useEffect(() => {
    if (initialRating) setRating(initialRating);
    if (initialCorrection) setCorrectionText(initialCorrection);
  }, [initialRating, initialCorrection]);

  const showToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 3000);
  };

  const toggleTag = (tag: string) => {
    setSelectedTags((prev) =>
      prev.includes(tag) ? prev.filter((t) => t !== tag) : [...prev, tag]
    );
  };

  const handleThumbsUp = async () => {
    const nextRating = rating === "thumbs_up" ? null : "thumbs_up";
    setRating(nextRating);
    setShowCorrectionUI(false);

    if (nextRating === "thumbs_up") {
      try {
        await chatApi.submitFeedback({
          message_id: messageId,
          conversation_id: conversationId,
          rating: "thumbs_up",
          user_query: userQuery,
        });
        showToast("Thanks for the positive feedback!");
        onFeedbackSaved?.("thumbs_up");
      } catch (err) {
        console.warn("Failed to persist thumbs_up feedback:", err);
      }
    }
  };

  const handleThumbsDown = async () => {
    if (rating === "thumbs_down" && showCorrectionUI) {
      setShowCorrectionUI(false);
      return;
    }

    setRating("thumbs_down");
    setShowCorrectionUI(true);

    try {
      await chatApi.submitFeedback({
        message_id: messageId,
        conversation_id: conversationId,
        rating: "thumbs_down",
        user_query: userQuery,
      });
      onFeedbackSaved?.("thumbs_down");
    } catch (err) {
      console.warn("Failed to log initial thumbs_down:", err);
    }
  };

  const handleSubmitCorrection = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!correctionText.trim() && selectedTags.length === 0) {
      setShowCorrectionUI(false);
      return;
    }

    setIsSubmitting(true);
    try {
      await chatApi.submitFeedback({
        message_id: messageId,
        conversation_id: conversationId,
        rating: "thumbs_down",
        feedback_text: correctionText.trim(),
        tags: selectedTags,
        user_query: userQuery,
      });
      setSubmittedFeedback(true);
      showToast("Thank you! Knowledge gap recorded for vector DB ingestion.");
      onFeedbackSaved?.("thumbs_down", correctionText.trim());
      setTimeout(() => setShowCorrectionUI(false), 2500);
    } catch (err) {
      console.error("Failed to submit correction:", err);
      showToast("Failed to submit correction. Please try again.");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="flex flex-col gap-2">
      {/* Action Buttons Row */}
      <div className="flex items-center gap-1">
        <button
          type="button"
          onClick={handleThumbsUp}
          className={`p-1.5 rounded-md transition-all border ${
            rating === "thumbs_up"
              ? "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 border-emerald-500/30 shadow-xs"
              : "text-muted-foreground hover:text-emerald-600 hover:bg-emerald-500/10 border-transparent hover:border-emerald-500/20"
          }`}
          title="Good response (Accurate & Complete)"
          aria-label="Thumbs up"
        >
          <ThumbsUp className="h-3.5 w-3.5" />
        </button>

        <button
          type="button"
          onClick={handleThumbsDown}
          className={`p-1.5 rounded-md transition-all border ${
            rating === "thumbs_down"
              ? "bg-rose-500/15 text-rose-600 dark:text-rose-400 border-rose-500/30 shadow-xs"
              : "text-muted-foreground hover:text-rose-600 hover:bg-rose-500/10 border-transparent hover:border-rose-500/20"
          }`}
          title="Report issue (Incomplete or Incorrect)"
          aria-label="Thumbs down"
        >
          <ThumbsDown className="h-3.5 w-3.5" />
        </button>

        {toastMessage && (
          <span className="text-[11px] font-medium text-muted-foreground animate-in fade-in slide-in-from-left-1 ml-1 flex items-center gap-1">
            <Check className="h-3 w-3 text-emerald-500" />
            {toastMessage}
          </span>
        )}
      </div>

      {/* Correction UI Prompt: "What was missing or incorrect?" */}
      {showCorrectionUI && (
        <div className="w-full max-w-xl rounded-xl border border-rose-500/20 bg-card/95 shadow-md p-3.5 mt-1 space-y-3 animate-in fade-in slide-in-from-top-1 backdrop-blur duration-200">
          <div className="flex items-start justify-between gap-2">
            <div>
              <div className="flex items-center gap-1.5 text-xs font-semibold text-foreground">
                <MessageSquareQuote className="h-3.5 w-3.5 text-rose-500" />
                <span>What was missing or incorrect?</span>
              </div>
              <p className="text-[11px] text-muted-foreground mt-0.5">
                Your direct feedback captures specific gaps in our vector database and helps improve accuracy.
              </p>
            </div>
            <button
              type="button"
              onClick={() => setShowCorrectionUI(false)}
              className="p-1 rounded-md text-muted-foreground hover:text-foreground hover:bg-accent transition-colors"
              title="Close"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          </div>

          {/* Quick Tag Pills */}
          <div className="flex flex-wrap gap-1.5 pt-0.5">
            {COMMON_GAP_TAGS.map((tag) => {
              const isSelected = selectedTags.includes(tag);
              return (
                <button
                  key={tag}
                  type="button"
                  onClick={() => toggleTag(tag)}
                  className={`text-[10px] font-medium px-2 py-0.5 rounded-full border transition-all ${
                    isSelected
                      ? "bg-primary text-primary-foreground border-primary"
                      : "bg-muted/50 text-muted-foreground hover:text-foreground border-border hover:bg-accent"
                  }`}
                >
                  {tag}
                </button>
              );
            })}
          </div>

          {/* Freeform Correction Text Area */}
          <form onSubmit={handleSubmitCorrection} className="space-y-2">
            <textarea
              value={correctionText}
              onChange={(e) => setCorrectionText(e.target.value)}
              placeholder="What facts, sections, or documents should have been retrieved?"
              rows={2}
              className="w-full text-xs rounded-lg border border-border bg-background p-2.5 text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary focus:border-primary transition-all resize-none"
            />

            <div className="flex items-center justify-between pt-1">
              <span className="text-[10px] text-muted-foreground flex items-center gap-1">
                <Sparkles className="h-3 w-3 text-amber-500" />
                Feeds into vector DB gap analysis
              </span>

              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => setShowCorrectionUI(false)}
                  className="px-2.5 py-1 text-xs rounded-md text-muted-foreground hover:text-foreground hover:bg-accent transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSubmitting || (!correctionText.trim() && selectedTags.length === 0)}
                  className="inline-flex items-center gap-1.5 px-3 py-1 text-xs font-medium rounded-md bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50 disabled:pointer-events-none transition-all shadow-xs"
                >
                  {isSubmitting ? (
                    "Submitting..."
                  ) : submittedFeedback ? (
                    <>
                      <Check className="h-3 w-3" />
                      Updated
                    </>
                  ) : (
                    <>
                      <Send className="h-3 w-3" />
                      Submit Correction
                    </>
                  )}
                </button>
              </div>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}
