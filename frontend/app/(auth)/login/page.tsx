"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { Lock, Mail, ShieldAlert } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { authApi } from "@/lib/api";
import { clearToken, getToken, setToken, setUser } from "@/lib/auth";
import { loginSchema, LoginFormData } from "@/lib/validators";

export default function LoginPage() {
  const router = useRouter();
  const [serverError, setServerError] = React.useState<string | null>(null);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<LoginFormData>({
    resolver: zodResolver(loginSchema),
  });

  React.useEffect(() => {
    if (typeof window !== "undefined") {
      const urlParams = new URLSearchParams(window.location.search);
      // If redirected with ?from=..., session is not valid; clear stale tokens to stop loop
      if (urlParams.has("from")) {
        clearToken();
        return;
      }
      const token = getToken();
      if (token) {
        document.cookie = `rag_access_token=${encodeURIComponent(token)}; path=/; max-age=86400; SameSite=Lax`;
        window.location.href = "/dashboard";
      }
    }
  }, []);

  const onSubmit = async (data: LoginFormData) => {
    setServerError(null);
    try {
      // Purge any existing session or legacy chat keys to prevent cross-account pollution
      clearToken();

      const res = await authApi.login(data);
      setToken(res.access_token);

      // Fetch user profile and roles
      try {
        const me = await authApi.me();
        setUser({
          id: me.id,
          email: me.email,
          full_name: me.full_name,
          roles: me.roles.map((r) => r.name),
        });
      } catch (meErr) {
        console.warn("Could not fetch profile immediately, continuing:", meErr);
      }

      window.location.href = "/dashboard";
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to sign in. Please check credentials.";
      setServerError(msg);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-background p-4">
      <Card className="w-full max-w-md border-border bg-card">
        <CardHeader className="space-y-1 text-center">
          <div className="mx-auto mb-2 flex h-10 w-10 items-center justify-center rounded-full bg-primary/10 text-primary">
            <Lock className="h-5 w-5" />
          </div>
          <CardTitle className="text-xl font-bold tracking-tight">Enterprise RAG Platform</CardTitle>
          <p className="text-xs text-muted-foreground">
            Sign in with your organization credentials
          </p>
        </CardHeader>
        <CardContent>
          {serverError && (
            <div className="mb-4 flex items-center gap-2 rounded-md border border-destructive/30 bg-destructive/10 p-3 text-xs text-destructive">
              <ShieldAlert className="h-4 w-4 shrink-0" />
              <span>{serverError}</span>
            </div>
          )}

          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            <div>
              <Input
                label="Email Address"
                type="email"
                placeholder="analyst@organization.com"
                autoComplete="email"
                error={errors.email?.message}
                {...register("email")}
              />
            </div>
            <div>
              <Input
                label="Password"
                type="password"
                placeholder="••••••••••••"
                autoComplete="current-password"
                error={errors.password?.message}
                {...register("password")}
              />
            </div>

            <Button type="submit" className="w-full" disabled={isSubmitting}>
              {isSubmitting ? "Authenticating..." : "Sign In"}
            </Button>

            <div className="pt-2 text-center text-xs text-muted-foreground">
              Need an account?{" "}
              <Link href="/register" className="font-medium text-primary hover:underline">
                Register here
              </Link>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
