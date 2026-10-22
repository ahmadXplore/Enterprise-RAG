"use client";
import * as React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  Search,
  MessageSquare,
  FileText,
  BarChart3,
  Settings,
  Users,
  Briefcase,
  LogOut,
  Database,
  Activity,
  ScrollText,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { clearToken, getUser, isAdmin, isAnalyst } from "@/lib/auth";

interface NavItem {
  label: string;
  href: string;
  icon: React.ComponentType<{ className?: string }>;
  adminOnly?: boolean;
  analystOnly?: boolean;
}

const navItems: NavItem[] = [
  { label: "Dashboard", href: "/dashboard", icon: LayoutDashboard },
  { label: "Search", href: "/search", icon: Search },
  { label: "Chat", href: "/chat", icon: MessageSquare },
  { label: "Documents", href: "/documents", icon: FileText },
  { label: "Evaluations", href: "/evaluations", icon: BarChart3, analystOnly: true },
  { label: "Admin — Observability", href: "/admin/observability", icon: Activity, adminOnly: true },
  { label: "Admin — Audit Logs", href: "/admin/audit-logs", icon: ScrollText, adminOnly: true },
  { label: "Admin — Users", href: "/admin/users", icon: Users, adminOnly: true },
  { label: "Admin — Jobs", href: "/admin/jobs", icon: Briefcase, adminOnly: true },
  { label: "Settings", href: "/settings", icon: Settings },
];

export function Sidebar() {
  const pathname = usePathname();
  const [mounted, setMounted] = React.useState(false);

  React.useEffect(() => {
    setMounted(true);
  }, []);

  const user = mounted ? getUser() : null;
  const admin = mounted ? isAdmin() : false;
  const analyst = mounted ? isAnalyst() : false;

  const visibleItems = navItems.filter((item) => {
    if (item.adminOnly && !admin) return false;
    if (item.analystOnly && !analyst) return false;
    return true;
  });

  return (
    <nav
      className="flex h-full w-[4.25rem] shrink-0 flex-col border-r border-[#263a32] bg-[#172923] text-[#f4f6f1] sm:w-56"
      aria-label="Main navigation"
    >
      <div className="flex h-16 items-center justify-center border-b border-white/10 px-3 sm:justify-start sm:px-5">
        <Database className="h-5 w-5 shrink-0 text-[#a6c9a5]" aria-hidden="true" />
        <span className="ml-2 hidden text-sm font-semibold text-white sm:inline">
          Fieldnotes <span className="font-normal text-white/55">/ RAG</span>
        </span>
      </div>

      <ul className="flex-1 space-y-1 overflow-y-auto px-2 py-5 sm:px-3" role="list">
        {visibleItems.map((item) => {
          const active = pathname.startsWith(item.href);
          return (
            <li key={item.href}>
              <Link
                href={item.href}
                className={cn(
                  "flex items-center justify-center gap-3 rounded-md px-2.5 py-2.5 text-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#a6c9a5] sm:justify-start",
                  active
                    ? "bg-white/15 font-semibold text-white"
                    : "text-white/80 hover:bg-white/10 hover:text-white font-medium"
                )}
                aria-current={active ? "page" : undefined}
                title={item.label}
              >
                <item.icon className="h-4 w-4 shrink-0" aria-hidden="true" />
                <span className="hidden sm:inline">{item.label}</span>
              </Link>
            </li>
          );
        })}
      </ul>

      <div className="border-t border-white/10 p-2 sm:p-3">
        {user && (
          <div className="mb-2 hidden truncate px-2 text-xs text-white/70 sm:block">{user.email}</div>
        )}
        <button
          onClick={() => {
            clearToken();
            window.location.href = "/login";
          }}
          className={cn(
            "flex w-full items-center justify-center gap-3 rounded-md px-2.5 py-2.5 text-sm text-white/80 transition-colors hover:bg-white/10 hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#a6c9a5] sm:justify-start"
          )}
          title="Sign out"
        >
          <LogOut className="h-4 w-4" aria-hidden="true" />
          <span className="hidden sm:inline">Sign out</span>
        </button>
      </div>
    </nav>
  );
}
