"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { getToken } from "@/lib/auth";

export default function RootPage() {
  const router = useRouter();

  React.useEffect(() => {
    const token = getToken();
    if (token) {
      document.cookie = `rag_access_token=${encodeURIComponent(token)}; path=/; max-age=86400; SameSite=Lax`;
      router.replace("/dashboard");
    } else {
      router.replace("/login");
    }
  }, [router]);

  return (
    <div className="flex min-h-screen items-center justify-center bg-background">
      <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
    </div>
  );
}
