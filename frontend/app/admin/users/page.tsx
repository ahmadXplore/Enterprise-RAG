"use client";

import * as React from "react";
import { Users, Shield, RefreshCw } from "lucide-react";
import { AppShell } from "@/components/layout/app-shell";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Spinner, ErrorState, EmptyState } from "@/components/ui/states";
import { usersApi } from "@/lib/api";
import { isAdmin } from "@/lib/auth";

export default function AdminUsersPage() {
  const [users, setUsers] = React.useState<
    Array<{
      id: string;
      email: string;
      full_name: string;
      is_active: boolean;
      created_at: string;
      roles: Array<{ id: string; name: string }>;
    }>
  >([]);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);

  const admin = isAdmin();

  const fetchUsers = React.useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await usersApi.list();
      setUsers(data);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load user accounts");
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => {
    fetchUsers();
  }, [fetchUsers]);

  return (
    <AppShell>
      <div className="p-6 max-w-6xl mx-auto space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold tracking-tight text-foreground flex items-center gap-2">
              <Users className="h-5 w-5 text-primary" />
              User & Role Management
            </h1>
            <p className="text-xs text-muted-foreground mt-0.5">
              Enforce role-based access control (Admin, Analyst, Viewer) across documents
            </p>
          </div>

          <Button variant="outline" size="sm" onClick={fetchUsers} className="gap-1.5 text-xs">
            <RefreshCw className="h-3.5 w-3.5" /> Refresh
          </Button>
        </div>

        <Card className="border-border bg-card">
          <CardHeader className="pb-3 border-b border-border">
            <div className="flex items-center justify-between">
              <CardTitle className="text-sm font-semibold">Registered Accounts</CardTitle>
              <span className="text-xs text-muted-foreground font-mono">{users.length} accounts</span>
            </div>
          </CardHeader>
          <CardContent className="p-0">
            {loading ? (
              <div className="py-12 flex justify-center">
                <Spinner className="h-6 w-6" />
              </div>
            ) : error ? (
              <div className="p-6">
                <ErrorState message={error} onRetry={fetchUsers} />
              </div>
            ) : users.length === 0 ? (
              <div className="p-6">
                <EmptyState title="No registered users found" />
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="bg-muted/70 border-b border-border text-muted-foreground uppercase font-semibold">
                    <tr>
                      <th scope="col" className="px-4 py-3">Full Name</th>
                      <th scope="col" className="px-4 py-3">Email Address</th>
                      <th scope="col" className="px-4 py-3">Assigned Roles</th>
                      <th scope="col" className="px-4 py-3">Status</th>
                      <th scope="col" className="px-4 py-3">Created</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {users.map((u) => (
                      <tr key={u.id} className="hover:bg-accent/30 transition-colors">
                        <td className="px-4 py-3.5 font-medium text-foreground">{u.full_name}</td>
                        <td className="px-4 py-3.5 font-mono text-muted-foreground">{u.email}</td>
                        <td className="px-4 py-3.5">
                          <div className="flex gap-1 flex-wrap">
                            {u.roles.map((r) => (
                              <Badge
                                key={r.id || r.name}
                                variant={r.name === "admin" ? "default" : "outline"}
                                className="text-[10px] uppercase font-mono"
                              >
                                {r.name}
                              </Badge>
                            ))}
                          </div>
                        </td>
                        <td className="px-4 py-3.5">
                          <Badge variant={u.is_active ? "success" : "secondary"}>
                            {u.is_active ? "Active" : "Disabled"}
                          </Badge>
                        </td>
                        <td className="px-4 py-3.5 text-muted-foreground">
                          {new Date(u.created_at).toLocaleDateString()}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </AppShell>
  );
}
