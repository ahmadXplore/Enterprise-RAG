"use client";

import * as React from "react";
import { AppShell } from "@/components/layout/app-shell";
import { ChatInterface } from "@/components/chat/chat-interface";

export default function ChatPage() {
  return (
    <AppShell>
      <div className="h-[calc(100vh-3.5rem)] flex flex-col">
        <ChatInterface />
      </div>
    </AppShell>
  );
}
