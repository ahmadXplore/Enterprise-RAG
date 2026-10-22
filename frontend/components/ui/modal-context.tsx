"use client";

import * as React from "react";
import {
  AlertTriangle,
  AlertCircle,
  CheckCircle2,
  Info,
  X,
  ShieldAlert,
} from "lucide-react";
import { Button } from "./button";

export interface ConfirmOptions {
  title: string;
  message: string | React.ReactNode;
  confirmText?: string;
  cancelText?: string;
  variant?: "default" | "destructive" | "warning" | "success";
}

export interface NoticeOptions {
  title?: string;
  message: string | React.ReactNode;
  buttonText?: string;
  variant?: "info" | "error" | "success" | "warning";
}

export interface ToastItem {
  id: string;
  message: string;
  title?: string;
  type: "success" | "error" | "info" | "warning";
}

interface ModalContextValue {
  confirm: (options: ConfirmOptions) => Promise<boolean>;
  alert: (message: string, title?: string, variant?: "error" | "info" | "success" | "warning") => Promise<void>;
  toast: {
    success: (message: string, title?: string) => void;
    error: (message: string, title?: string) => void;
    info: (message: string, title?: string) => void;
    warning: (message: string, title?: string) => void;
  };
}

const ModalContext = React.createContext<ModalContextValue | null>(null);

export function ModalProvider({ children }: { children: React.ReactNode }) {
  // Confirmation Modal State
  const [confirmState, setConfirmState] = React.useState<{
    isOpen: boolean;
    options: ConfirmOptions;
    resolve: (val: boolean) => void;
  } | null>(null);

  // Alert / Notice Modal State
  const [noticeState, setNoticeState] = React.useState<{
    isOpen: boolean;
    options: NoticeOptions;
    resolve: () => void;
  } | null>(null);

  // Toasts State
  const [toasts, setToasts] = React.useState<ToastItem[]>([]);

  const addToast = React.useCallback(
    (message: string, type: "success" | "error" | "info" | "warning", title?: string) => {
      const id = Math.random().toString(36).substring(2, 9);
      setToasts((prev) => [...prev, { id, message, title, type }]);
      setTimeout(() => {
        setToasts((prev) => prev.filter((t) => t.id !== id));
      }, 4500);
    },
    []
  );

  const confirm = React.useCallback((options: ConfirmOptions): Promise<boolean> => {
    return new Promise((resolve) => {
      setConfirmState({
        isOpen: true,
        options,
        resolve,
      });
    });
  }, []);

  const showAlert = React.useCallback(
    (
      message: string,
      title: string = "Notice",
      variant: "error" | "info" | "success" | "warning" = "info"
    ): Promise<void> => {
      return new Promise((resolve) => {
        setNoticeState({
          isOpen: true,
          options: { title, message, variant },
          resolve,
        });
      });
    },
    []
  );

  const toast = React.useMemo(
    () => ({
      success: (msg: string, title?: string) => addToast(msg, "success", title),
      error: (msg: string, title?: string) => addToast(msg, "error", title),
      info: (msg: string, title?: string) => addToast(msg, "info", title),
      warning: (msg: string, title?: string) => addToast(msg, "warning", title),
    }),
    [addToast]
  );

  const handleConfirmClose = (result: boolean) => {
    if (confirmState) {
      confirmState.resolve(result);
      setConfirmState(null);
    }
  };

  const handleNoticeClose = () => {
    if (noticeState) {
      noticeState.resolve();
      setNoticeState(null);
    }
  };

  return (
    <ModalContext.Provider value={{ confirm, alert: showAlert, toast }}>
      {children}

      {/* Confirmation Modal Popup */}
      {confirmState && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs p-4 animate-in fade-in duration-150"
          role="dialog"
          aria-modal="true"
        >
          <div className="w-full max-w-md rounded-2xl border border-border bg-card shadow-2xl p-6 space-y-4 animate-in zoom-in-95 duration-150">
            <div className="flex items-start gap-3.5">
              <div
                className={`h-10 w-10 rounded-xl flex items-center justify-center shrink-0 border ${
                  confirmState.options.variant === "destructive"
                    ? "bg-destructive/10 text-destructive border-destructive/20"
                    : confirmState.options.variant === "warning"
                    ? "bg-amber-500/10 text-amber-500 border-amber-500/20"
                    : confirmState.options.variant === "success"
                    ? "bg-emerald-500/10 text-emerald-500 border-emerald-500/20"
                    : "bg-primary/10 text-primary border-primary/20"
                }`}
              >
                {confirmState.options.variant === "destructive" ? (
                  <ShieldAlert className="h-5 w-5" />
                ) : confirmState.options.variant === "warning" ? (
                  <AlertTriangle className="h-5 w-5" />
                ) : confirmState.options.variant === "success" ? (
                  <CheckCircle2 className="h-5 w-5" />
                ) : (
                  <Info className="h-5 w-5" />
                )}
              </div>
              <div className="min-w-0 flex-1">
                <h3 className="text-base font-bold text-foreground">
                  {confirmState.options.title}
                </h3>
                <div className="text-xs text-muted-foreground mt-1 leading-relaxed">
                  {confirmState.options.message}
                </div>
              </div>
            </div>

            <div className="flex items-center justify-end gap-2.5 pt-3 border-t border-border">
              <Button
                variant="outline"
                size="sm"
                onClick={() => handleConfirmClose(false)}
                className="text-xs font-medium"
              >
                {confirmState.options.cancelText || "Cancel"}
              </Button>
              <Button
                variant={
                  confirmState.options.variant === "destructive"
                    ? "destructive"
                    : confirmState.options.variant === "warning"
                    ? "default"
                    : "default"
                }
                size="sm"
                onClick={() => handleConfirmClose(true)}
                className={`text-xs font-semibold shadow-xs ${
                  confirmState.options.variant === "warning"
                    ? "bg-amber-600 hover:bg-amber-700 text-white"
                    : confirmState.options.variant === "success"
                    ? "bg-emerald-600 hover:bg-emerald-700 text-white"
                    : ""
                }`}
              >
                {confirmState.options.confirmText || "Confirm"}
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Notice / Alert Modal Popup */}
      {noticeState && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs p-4 animate-in fade-in duration-150"
          role="dialog"
          aria-modal="true"
        >
          <div className="w-full max-w-sm rounded-2xl border border-border bg-card shadow-2xl p-6 space-y-4 animate-in zoom-in-95 duration-150">
            <div className="flex items-start gap-3.5">
              <div
                className={`h-10 w-10 rounded-xl flex items-center justify-center shrink-0 border ${
                  noticeState.options.variant === "error"
                    ? "bg-destructive/10 text-destructive border-destructive/20"
                    : noticeState.options.variant === "warning"
                    ? "bg-amber-500/10 text-amber-500 border-amber-500/20"
                    : noticeState.options.variant === "success"
                    ? "bg-emerald-500/10 text-emerald-500 border-emerald-500/20"
                    : "bg-primary/10 text-primary border-primary/20"
                }`}
              >
                {noticeState.options.variant === "error" ? (
                  <AlertCircle className="h-5 w-5" />
                ) : noticeState.options.variant === "warning" ? (
                  <AlertTriangle className="h-5 w-5" />
                ) : noticeState.options.variant === "success" ? (
                  <CheckCircle2 className="h-5 w-5" />
                ) : (
                  <Info className="h-5 w-5" />
                )}
              </div>
              <div className="min-w-0 flex-1">
                <h3 className="text-base font-bold text-foreground">
                  {noticeState.options.title || "Notice"}
                </h3>
                <div className="text-xs text-muted-foreground mt-1 leading-relaxed">
                  {noticeState.options.message}
                </div>
              </div>
            </div>

            <div className="flex items-center justify-end pt-2 border-t border-border">
              <Button
                size="sm"
                onClick={handleNoticeClose}
                className="text-xs font-semibold px-4"
              >
                {noticeState.options.buttonText || "Understood"}
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Floating Notification Toasts */}
      {toasts.length > 0 && (
        <div className="fixed bottom-5 right-5 z-50 flex flex-col gap-2 max-w-sm w-full pointer-events-none">
          {toasts.map((t) => (
            <div
              key={t.id}
              className={`pointer-events-auto p-3.5 rounded-xl border shadow-xl flex items-start gap-3 animate-in slide-in-from-bottom-3 fade-in duration-200 ${
                t.type === "success"
                  ? "bg-card border-emerald-500/30 text-foreground"
                  : t.type === "error"
                  ? "bg-card border-destructive/30 text-foreground"
                  : t.type === "warning"
                  ? "bg-card border-amber-500/30 text-foreground"
                  : "bg-card border-border text-foreground"
              }`}
            >
              <div className="shrink-0 mt-0.5">
                {t.type === "success" && (
                  <CheckCircle2 className="h-4 w-4 text-emerald-500" />
                )}
                {t.type === "error" && (
                  <AlertCircle className="h-4 w-4 text-destructive" />
                )}
                {t.type === "warning" && (
                  <AlertTriangle className="h-4 w-4 text-amber-500" />
                )}
                {t.type === "info" && <Info className="h-4 w-4 text-primary" />}
              </div>
              <div className="flex-1 min-w-0">
                {t.title && (
                  <div className="text-xs font-bold leading-tight mb-0.5">
                    {t.title}
                  </div>
                )}
                <div className="text-xs text-muted-foreground leading-snug">
                  {t.message}
                </div>
              </div>
              <button
                type="button"
                onClick={() => setToasts((prev) => prev.filter((item) => item.id !== t.id))}
                className="text-muted-foreground hover:text-foreground shrink-0 p-0.5"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            </div>
          ))}
        </div>
      )}
    </ModalContext.Provider>
  );
}

export function useModal() {
  const ctx = React.useContext(ModalContext);
  if (!ctx) {
    throw new Error("useModal must be used within a ModalProvider");
  }
  return ctx;
}
