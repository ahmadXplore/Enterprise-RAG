"use client";

import * as React from "react";
import { usePathname } from "next/navigation";
import { ShieldCheck, User } from "lucide-react";
import { getUser } from "@/lib/auth";

export function Header() {
  const pathname = usePathname();
  const [mounted, setMounted] = React.useState(false);

  React.useEffect(() => {
    setMounted(true);
  }, []);

  const user = mounted ? getUser() : null;

  // Format breadcrumb or page title from pathname
  const getPageTitle = (path: string) => {
    if (path.startsWith("/dashboard")) return "Overview";
    if (path.startsWith("/search")) return "Search";
    if (path.startsWith("/chat")) return "Chat";
    if (path.startsWith("/documents")) return "Documents";
    if (path.startsWith("/evaluations")) return "Evaluations";
    if (path.startsWith("/admin/users")) return "Users";
    if (path.startsWith("/admin/jobs")) return "Ingestion jobs";
    if (path.startsWith("/settings")) return "Settings";
    return "Workspace";
  };

  return (
    <header className="sticky top-0 z-30 flex h-16 items-center justify-between border-b border-border bg-background/90 px-4 backdrop-blur sm:px-8">
      <div className="flex items-center gap-3">
        <span className="text-sm font-medium text-foreground">
          {getPageTitle(pathname)}
        </span>
      </div>

      <div className="flex items-center gap-3 sm:gap-5">
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <ShieldCheck className="h-4 w-4 text-primary" />
          <span className="hidden sm:inline">Access protected</span>
        </div>

        {user && (
          <div className="flex items-center gap-2 border-l border-border pl-3 text-xs text-muted-foreground sm:pl-5">
            <div className="flex h-8 w-8 items-center justify-center rounded-full bg-secondary text-foreground">
              <User className="h-4 w-4" />
            </div>
            <div className="hidden sm:block">
              <span className="block leading-tight font-medium text-foreground">{user.full_name || user.email}</span>
              <span className="text-[10px] uppercase text-muted-foreground">{user.roles?.join(", ") || "Viewer"}</span>
            </div>
          </div>
        )}
      </div>
    </header>
  );
}
