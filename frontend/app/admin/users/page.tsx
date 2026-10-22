"use client";

import * as React from "react";
import {
  Users,
  UserPlus,
  RefreshCw,
  Shield,
  ShieldAlert,
  ShieldCheck,
  Ban,
  Trash2,
  Search,
  AlertTriangle,
  X,
  Mail,
  Lock,
  UserCheck,
  Check,
} from "lucide-react";
import { AppShell } from "@/components/layout/app-shell";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Spinner, ErrorState, EmptyState } from "@/components/ui/states";
import { usersApi, AdminUserItem } from "@/lib/api";
import { getUser } from "@/lib/auth";
import { useModal } from "@/components/ui/modal-context";

export default function AdminUsersPage() {
  const modal = useModal();
  const [users, setUsers] = React.useState<AdminUserItem[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);

  // Filters & Search
  const [searchQuery, setSearchQuery] = React.useState("");
  const [roleFilter, setRoleFilter] = React.useState<string>("all");
  const [statusFilter, setStatusFilter] = React.useState<string>("all");

  // Add User Modal State
  const [isAddModalOpen, setIsAddModalOpen] = React.useState(false);
  const [newFullName, setNewFullName] = React.useState("");
  const [newEmail, setNewEmail] = React.useState("");
  const [newPassword, setNewPassword] = React.useState("");
  const [newRole, setNewRole] = React.useState("VIEWER");
  const [isCreating, setIsCreating] = React.useState(false);
  const [addModalError, setAddModalError] = React.useState<string | null>(null);

  // Status Update Loading State
  const [updatingUserId, setUpdatingUserId] = React.useState<string | null>(null);

  const currentUser = React.useMemo(() => getUser(), []);

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

  // Handle Add User
  const handleCreateUser = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newEmail.trim()) {
      setAddModalError("Email address is required.");
      return;
    }
    if (!newPassword || newPassword.length < 8) {
      setAddModalError("Password must be at least 8 characters.");
      return;
    }

    setIsCreating(true);
    setAddModalError(null);
    try {
      await usersApi.create({
        email: newEmail.trim().toLowerCase(),
        password: newPassword,
        full_name: newFullName.trim() || undefined,
        role: newRole,
      });

      setIsAddModalOpen(false);
      setNewFullName("");
      setNewEmail("");
      setNewPassword("");
      setNewRole("VIEWER");
      modal.toast.success(`Account for "${newEmail.trim()}" created successfully.`);
      await fetchUsers();
    } catch (err: unknown) {
      setAddModalError(err instanceof Error ? err.message : "Failed to create user account");
    } finally {
      setIsCreating(false);
    }
  };

  // Handle Block / Reinstate Toggle
  const handleToggleStatus = async (user: AdminUserItem) => {
    if (currentUser && currentUser.id === user.id && user.is_active) {
      await modal.alert(
        "Security policy strictly forbids blocking your own logged-in account.",
        "Action Not Allowed",
        "warning"
      );
      return;
    }

    const nextStatus = !user.is_active;
    const actionLabel = nextStatus ? "reinstate" : "block";

    const confirmed = await modal.confirm({
      title: nextStatus ? "Reinstate User Account" : "Block User Account",
      message: (
        <span>
          Are you sure you want to <strong>{actionLabel}</strong> account{" "}
          <strong className="text-foreground">{user.email}</strong>?{" "}
          {nextStatus
            ? "Their login access and document authorizations will be restored immediately."
            : "Their active sessions will be terminated and they will not be able to log in."}
        </span>
      ),
      confirmText: nextStatus ? "Reinstate Account" : "Block Account",
      variant: nextStatus ? "success" : "warning",
    });

    if (!confirmed) return;

    setUpdatingUserId(user.id);
    try {
      await usersApi.updateStatus(user.id, nextStatus);
      modal.toast.success(
        `User "${user.email}" has been successfully ${nextStatus ? "reinstated" : "blocked"}.`
      );
      await fetchUsers();
    } catch (err: unknown) {
      modal.toast.error(err instanceof Error ? err.message : `Failed to ${actionLabel} user.`);
    } finally {
      setUpdatingUserId(null);
    }
  };

  // Handle Role Change
  const handleRoleChange = async (user: AdminUserItem, newRoleName: string) => {
    try {
      await usersApi.updateRole(user.id, newRoleName);
      modal.toast.success(`Role for "${user.email}" updated to ${newRoleName}.`);
      await fetchUsers();
    } catch (err: unknown) {
      modal.toast.error(err instanceof Error ? err.message : "Failed to update role");
    }
  };

  // Handle Delete Confirmation
  const handleDeleteUser = async (user: AdminUserItem) => {
    if (currentUser && (currentUser.id === user.id || currentUser.email === user.email)) {
      await modal.alert(
        "Security policy forbids deleting your own logged-in administrative account.",
        "Action Not Allowed",
        "warning"
      );
      return;
    }

    const confirmed = await modal.confirm({
      title: "Confirm Account Deletion",
      message: (
        <span>
          Are you sure you want to permanently delete{" "}
          <strong className="text-foreground">{user.email}</strong>? All conversations,
          document authorizations, and access records for this user will be removed. This action cannot be undone.
        </span>
      ),
      confirmText: "Delete User",
      variant: "destructive",
    });

    if (!confirmed) return;

    try {
      await usersApi.delete(user.id);
      modal.toast.success(`User "${user.email}" has been permanently deleted.`);
      await fetchUsers();
    } catch (err: unknown) {
      modal.toast.error(err instanceof Error ? err.message : "Failed to delete user");
    }
  };

  // Filtered list
  const filteredUsers = React.useMemo(() => {
    return users.filter((u) => {
      const matchesSearch =
        (u.full_name || "").toLowerCase().includes(searchQuery.toLowerCase()) ||
        u.email.toLowerCase().includes(searchQuery.toLowerCase());

      const userRoleNames = u.roles.map((r) => r.name.toUpperCase());
      const matchesRole =
        roleFilter === "all" || userRoleNames.includes(roleFilter.toUpperCase());

      const matchesStatus =
        statusFilter === "all" ||
        (statusFilter === "active" && u.is_active) ||
        (statusFilter === "blocked" && !u.is_active);

      return matchesSearch && matchesRole && matchesStatus;
    });
  }, [users, searchQuery, roleFilter, statusFilter]);

  const activeCount = users.filter((u) => u.is_active).length;
  const blockedCount = users.filter((u) => !u.is_active).length;
  const adminCount = users.filter((u) =>
    u.roles.some((r) => r.name.toLowerCase() === "admin")
  ).length;

  return (
    <AppShell>
      <div className="p-6 max-w-6xl mx-auto space-y-6">
        {/* Header & Main Actions */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <h1 className="text-xl font-bold tracking-tight text-foreground flex items-center gap-2">
              <Users className="h-5 w-5 text-primary" />
              User & Access Governance
            </h1>
            <p className="text-xs text-muted-foreground mt-0.5">
              Add new accounts, delete obsolete profiles, block or reinstate access, and govern role-based access control
            </p>
          </div>

          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" onClick={fetchUsers} className="gap-1.5 text-xs">
              <RefreshCw className="h-3.5 w-3.5" /> Refresh
            </Button>
            <Button
              size="sm"
              onClick={() => {
                setAddModalError(null);
                setIsAddModalOpen(true);
              }}
              className="gap-1.5 text-xs shadow-xs"
            >
              <UserPlus className="h-3.5 w-3.5" /> Add User
            </Button>
          </div>
        </div>

        {/* Stats Metrics Overview */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <Card className="p-3.5 border-border bg-card">
            <div className="text-[11px] font-medium text-muted-foreground uppercase tracking-wider">
              Total Accounts
            </div>
            <div className="text-2xl font-bold text-foreground mt-1">{users.length}</div>
          </Card>
          <Card className="p-3.5 border-border bg-card">
            <div className="text-[11px] font-medium text-muted-foreground uppercase tracking-wider flex items-center gap-1.5">
              <ShieldCheck className="h-3.5 w-3.5 text-emerald-500" /> Active Users
            </div>
            <div className="text-2xl font-bold text-emerald-600 dark:text-emerald-400 mt-1">
              {activeCount}
            </div>
          </Card>
          <Card className="p-3.5 border-border bg-card">
            <div className="text-[11px] font-medium text-muted-foreground uppercase tracking-wider flex items-center gap-1.5">
              <ShieldAlert className="h-3.5 w-3.5 text-destructive" /> Blocked Users
            </div>
            <div className="text-2xl font-bold text-destructive mt-1">{blockedCount}</div>
          </Card>
          <Card className="p-3.5 border-border bg-card">
            <div className="text-[11px] font-medium text-muted-foreground uppercase tracking-wider flex items-center gap-1.5">
              <Shield className="h-3.5 w-3.5 text-primary" /> Administrators
            </div>
            <div className="text-2xl font-bold text-primary mt-1">{adminCount}</div>
          </Card>
        </div>

        {/* Filter & Search Bar */}
        <div className="flex flex-col sm:flex-row items-center justify-between gap-3 bg-card p-3 rounded-xl border border-border">
          <div className="relative w-full sm:w-80">
            <Search className="absolute left-3 top-2.5 h-3.5 w-3.5 text-muted-foreground" />
            <Input
              placeholder="Search by name or email..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-8 text-xs h-8 bg-muted/30"
            />
          </div>

          <div className="flex items-center gap-2 w-full sm:w-auto justify-end">
            <div className="flex items-center gap-1 text-xs text-muted-foreground">
              <span>Role:</span>
              <select
                value={roleFilter}
                onChange={(e) => setRoleFilter(e.target.value)}
                className="h-8 rounded-md border border-input bg-background px-2 text-xs focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
              >
                <option value="all">All Roles</option>
                <option value="ADMIN">Admin</option>
                <option value="ANALYST">Analyst</option>
                <option value="VIEWER">Viewer</option>
              </select>
            </div>

            <div className="flex items-center gap-1 text-xs text-muted-foreground">
              <span>Status:</span>
              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                className="h-8 rounded-md border border-input bg-background px-2 text-xs focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
              >
                <option value="all">All Statuses</option>
                <option value="active">Active Only</option>
                <option value="blocked">Blocked Only</option>
              </select>
            </div>
          </div>
        </div>

        {/* Users Table */}
        <Card className="border-border bg-card">
          <CardHeader className="pb-3 border-b border-border">
            <div className="flex items-center justify-between">
              <CardTitle className="text-sm font-semibold">Registered Accounts</CardTitle>
              <span className="text-xs text-muted-foreground font-mono">
                Showing {filteredUsers.length} of {users.length} accounts
              </span>
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
            ) : filteredUsers.length === 0 ? (
              <div className="p-6">
                <EmptyState
                  title="No users match criteria"
                  description="Try adjusting your search query or role/status filters."
                />
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="bg-muted/70 border-b border-border text-muted-foreground uppercase font-semibold">
                    <tr>
                      <th scope="col" className="px-4 py-3">User</th>
                      <th scope="col" className="px-4 py-3">Email Address</th>
                      <th scope="col" className="px-4 py-3">Assigned Role</th>
                      <th scope="col" className="px-4 py-3">Account Status</th>
                      <th scope="col" className="px-4 py-3">Created</th>
                      <th scope="col" className="px-4 py-3 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {filteredUsers.map((u) => {
                      const isSelf = currentUser?.id === u.id || currentUser?.email === u.email;
                      const isUpdating = updatingUserId === u.id;
                      const primaryRole = u.roles[0]?.name?.toUpperCase() || "VIEWER";

                      return (
                        <tr key={u.id} className="hover:bg-accent/30 transition-colors">
                          <td className="px-4 py-3.5 font-medium text-foreground">
                            <div className="flex items-center gap-2.5">
                              <div className="h-7 w-7 rounded-full bg-primary/10 text-primary font-bold flex items-center justify-center text-xs shrink-0 border border-primary/20">
                                {(u.full_name || u.email).slice(0, 1).toUpperCase()}
                              </div>
                              <div className="min-w-0">
                                <div className="font-semibold text-foreground flex items-center gap-1.5">
                                  <span className="truncate">{u.full_name || "—"}</span>
                                  {isSelf && (
                                    <Badge variant="secondary" className="text-[10px] py-0 px-1.5 font-mono">
                                      You
                                    </Badge>
                                  )}
                                </div>
                              </div>
                            </div>
                          </td>
                          <td className="px-4 py-3.5 font-mono text-muted-foreground">{u.email}</td>
                          <td className="px-4 py-3.5">
                            {isSelf ? (
                              <Badge variant="default" className="text-[10px] uppercase font-mono">
                                {primaryRole}
                              </Badge>
                            ) : (
                              <select
                                value={primaryRole}
                                onChange={(e) => handleRoleChange(u, e.target.value)}
                                className="h-6 rounded border border-border bg-card px-1.5 text-[11px] font-mono uppercase focus-visible:outline-none"
                              >
                                <option value="ADMIN">ADMIN</option>
                                <option value="ANALYST">ANALYST</option>
                                <option value="VIEWER">VIEWER</option>
                              </select>
                            )}
                          </td>
                          <td className="px-4 py-3.5">
                            <Badge
                              variant={u.is_active ? "success" : "destructive"}
                              className="capitalize gap-1 text-[11px]"
                            >
                              {u.is_active ? (
                                <>
                                  <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
                                  Active
                                </>
                              ) : (
                                <>
                                  <span className="h-1.5 w-1.5 rounded-full bg-destructive" />
                                  Blocked
                                </>
                              )}
                            </Badge>
                          </td>
                          <td className="px-4 py-3.5 text-muted-foreground font-mono text-[11px]">
                            {new Date(u.created_at).toLocaleDateString()}
                          </td>
                          <td className="px-4 py-3.5 text-right space-x-1.5">
                            {/* Block / Reinstate Action */}
                            {u.is_active ? (
                              <Button
                                variant="outline"
                                size="sm"
                                disabled={isSelf || isUpdating}
                                onClick={() => handleToggleStatus(u)}
                                className="h-7 text-xs px-2 text-destructive hover:bg-destructive/10 hover:text-destructive border-border"
                                title={isSelf ? "You cannot block yourself" : "Block user access"}
                              >
                                <Ban className="h-3 w-3 mr-1" />
                                <span>Block</span>
                              </Button>
                            ) : (
                              <Button
                                variant="outline"
                                size="sm"
                                disabled={isUpdating}
                                onClick={() => handleToggleStatus(u)}
                                className="h-7 text-xs px-2 text-emerald-600 hover:bg-emerald-50 dark:hover:bg-emerald-950/30 border-emerald-500/30"
                                title="Reinstate user access"
                              >
                                <Check className="h-3 w-3 mr-1" />
                                <span>Reinstate</span>
                              </Button>
                            )}

                            {/* Delete Action */}
                            <Button
                              variant="ghost"
                              size="sm"
                              disabled={isSelf}
                              onClick={() => handleDeleteUser(u)}
                              className="h-7 text-xs px-2 text-muted-foreground hover:text-destructive hover:bg-destructive/10"
                              title={isSelf ? "You cannot delete yourself" : "Permanently delete account"}
                            >
                              <Trash2 className="h-3.5 w-3.5" />
                            </Button>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Add User Modal */}
      {isAddModalOpen && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs p-4 animate-in fade-in duration-200"
          role="dialog"
          aria-modal="true"
        >
          <div className="w-full max-w-md rounded-2xl border border-border bg-card shadow-2xl p-6 space-y-4">
            <div className="flex items-center justify-between border-b border-border pb-3">
              <div className="flex items-center gap-2.5">
                <div className="h-8 w-8 rounded-lg bg-primary/10 border border-primary/20 flex items-center justify-center text-primary">
                  <UserPlus className="h-4 w-4" />
                </div>
                <div>
                  <h2 className="text-base font-bold text-foreground">Add New User</h2>
                  <p className="text-xs text-muted-foreground">Provision a new account with RBAC roles</p>
                </div>
              </div>
              <button
                onClick={() => setIsAddModalOpen(false)}
                disabled={isCreating}
                className="p-1.5 rounded-lg text-muted-foreground hover:text-foreground hover:bg-muted"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            {addModalError && (
              <div className="p-3 rounded-lg bg-destructive/10 border border-destructive/20 text-xs text-destructive flex items-start gap-2">
                <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5" />
                <span>{addModalError}</span>
              </div>
            )}

            <form onSubmit={handleCreateUser} className="space-y-3.5 text-xs">
              <div className="space-y-1">
                <label className="font-semibold text-foreground">Full Name</label>
                <Input
                  placeholder="e.g. Dr. Elena Rostova"
                  value={newFullName}
                  onChange={(e) => setNewFullName(e.target.value)}
                  className="h-8 text-xs"
                />
              </div>

              <div className="space-y-1">
                <label className="font-semibold text-foreground">Email Address *</label>
                <div className="relative">
                  <Mail className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-muted-foreground" />
                  <Input
                    type="email"
                    required
                    placeholder="name@organization.edu"
                    value={newEmail}
                    onChange={(e) => setNewEmail(e.target.value)}
                    className="pl-8 h-8 text-xs font-mono"
                  />
                </div>
              </div>

              <div className="space-y-1">
                <label className="font-semibold text-foreground">Password *</label>
                <div className="relative">
                  <Lock className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-muted-foreground" />
                  <Input
                    type="password"
                    required
                    minLength={8}
                    placeholder="Min. 8 characters"
                    value={newPassword}
                    onChange={(e) => setNewPassword(e.target.value)}
                    className="pl-8 h-8 text-xs font-mono"
                  />
                </div>
              </div>

              <div className="space-y-1">
                <label className="font-semibold text-foreground">Access Role *</label>
                <select
                  value={newRole}
                  onChange={(e) => setNewRole(e.target.value)}
                  className="w-full h-8 rounded-md border border-input bg-background px-2 text-xs font-mono focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                >
                  <option value="VIEWER">VIEWER — RAG chat, document view & citation inspection</option>
                  <option value="ANALYST">ANALYST — Research query execution & model evaluations</option>
                  <option value="ADMIN">ADMIN — Full system access, uploads, deletion & user governance</option>
                </select>
              </div>

              <div className="flex items-center justify-end gap-2 pt-3 border-t border-border">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => setIsAddModalOpen(false)}
                  disabled={isCreating}
                >
                  Cancel
                </Button>
                <Button type="submit" size="sm" disabled={isCreating} className="gap-1.5 shadow-xs">
                  {isCreating ? (
                    <>
                      <Spinner className="h-3 w-3" />
                      <span>Creating...</span>
                    </>
                  ) : (
                    <>
                      <UserCheck className="h-3.5 w-3.5" />
                      <span>Create User</span>
                    </>
                  )}
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}
    </AppShell>
  );
}
