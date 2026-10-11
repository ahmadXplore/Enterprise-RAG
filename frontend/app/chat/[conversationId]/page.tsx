"use client";

import * as React from "react";
import { useParams } from "next/navigation";
import { AppShell } from "@/components/layout/app-shell";
import { ChatInterface } from "@/components/chat/chat-interface";

export default function ConversationPage() {
  const params = useParams();
  const conversationId = Array.isArray(params.conversationId)
    ? params.conversationId[0]
    : params.conversationId;

  return (
    <AppShell>
      <div className="h-[calc(100vh-3.5rem)] flex flex-col">
        <ChatInterface conversationId={conversationId} />
      </div>
    </AppShell>
  );
}
