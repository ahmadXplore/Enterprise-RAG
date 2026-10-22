"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { UserPlus, ShieldAlert, CheckCircle2, ArrowRight, ArrowLeft, Calendar } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { authApi } from "@/lib/api";

const registerSchema = z.object({
  age: z
    .number({ invalid_type_error: "Age must be a number" })
    .int("Age must be a whole number")
    .min(13, "You must be at least 13 years old to create an account")
    .max(120, "Please enter a valid age"),
  full_name: z.string().min(2, "Full name must be at least 2 characters"),
  email: z.string().email("Valid corporate email required"),
  password: z.string().min(8, "Password must be at least 8 characters"),
});

type RegisterFormData = z.infer<typeof registerSchema>;

export default function RegisterPage() {
  const router = useRouter();
  const [step, setStep] = React.useState<1 | 2>(1);
  const [ageInput, setAgeInput] = React.useState<string>("");
  const [ageError, setAgeError] = React.useState<string | null>(null);
  const [serverError, setServerError] = React.useState<string | null>(null);
  const [success, setSuccess] = React.useState(false);

  const {
    register,
    handleSubmit,
    setValue,
    formState: { errors, isSubmitting },
  } = useForm<RegisterFormData>({
    resolver: zodResolver(registerSchema),
  });

  const handleAgeSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setAgeError(null);
    const parsedAge = parseInt(ageInput, 10);
    if (!ageInput || isNaN(parsedAge)) {
      setAgeError("Please enter your age");
      return;
    }
    if (parsedAge < 13) {
      setAgeError("You must be at least 13 years old to create an account");
      return;
    }
    if (parsedAge > 120) {
      setAgeError("Please enter a valid age (13 - 120)");
      return;
    }

    setValue("age", parsedAge, { shouldValidate: true });
    setStep(2);
  };

  const onSubmit = async (data: RegisterFormData) => {
    setServerError(null);
    try {
      await authApi.register({
        full_name: data.full_name,
        email: data.email,
        password: data.password,
        age: data.age,
      });
      setSuccess(true);
      setTimeout(() => {
        router.push("/login");
      }, 1500);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Registration failed. Try again.";
      setServerError(msg);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-background p-4">
      <Card className="w-full max-w-md border-border bg-card shadow-sm">
        <CardHeader className="space-y-1 text-center">
          <div className="mx-auto mb-2 flex h-10 w-10 items-center justify-center rounded-full bg-primary/10 text-primary">
            {step === 1 ? <Calendar className="h-5 w-5" /> : <UserPlus className="h-5 w-5" />}
          </div>
          <CardTitle className="text-xl font-bold tracking-tight">
            {step === 1 ? "Age Verification" : "Create an Account"}
          </CardTitle>
          <p className="text-xs text-muted-foreground">
            {step === 1
              ? "Please enter your age before creating an enterprise account"
              : "Register for access to the enterprise document corpus"}
          </p>
        </CardHeader>
        <CardContent>
          {serverError && (
            <div className="mb-4 flex items-center gap-2 rounded-md border border-destructive/30 bg-destructive/10 p-3 text-xs text-destructive">
              <ShieldAlert className="h-4 w-4 shrink-0" />
              <span>{serverError}</span>
            </div>
          )}

          {success && (
            <div className="mb-4 flex items-center gap-2 rounded-md border border-emerald-500/30 bg-emerald-500/10 p-3 text-xs text-emerald-700 dark:text-emerald-400">
              <CheckCircle2 className="h-4 w-4 shrink-0" />
              <span>Account created successfully! Redirecting to login...</span>
            </div>
          )}

          {/* STEP 1: Ask for User Age */}
          {step === 1 && (
            <form onSubmit={handleAgeSubmit} className="space-y-4">
              <div>
                <Input
                  label="Your Age (Years)"
                  type="number"
                  min={1}
                  max={120}
                  placeholder="e.g. 24"
                  value={ageInput}
                  onChange={(e) => {
                    setAgeInput(e.target.value);
                    setAgeError(null);
                  }}
                  error={ageError || undefined}
                  autoFocus
                />
                <p className="mt-1 text-[11px] text-muted-foreground">
                  You must be at least 13 years of age to access enterprise workspace features.
                </p>
              </div>

              <Button type="submit" className="w-full gap-2">
                <span>Continue</span>
                <ArrowRight className="h-4 w-4" />
              </Button>

              <div className="pt-2 text-center text-xs text-muted-foreground">
                Already have an account?{" "}
                <Link href="/login" className="font-medium text-primary hover:underline">
                  Sign in
                </Link>
              </div>
            </form>
          )}

          {/* STEP 2: Account Creation Details */}
          {step === 2 && (
            <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
              <div className="flex items-center justify-between rounded-lg border border-border/70 bg-accent/30 px-3 py-2 text-xs">
                <span className="text-muted-foreground">
                  Age: <strong className="text-foreground">{ageInput} years old</strong>
                </span>
                <button
                  type="button"
                  onClick={() => setStep(1)}
                  className="text-xs font-medium text-primary hover:underline inline-flex items-center gap-1"
                >
                  <ArrowLeft className="h-3 w-3" /> Change
                </button>
              </div>

              <div>
                <Input
                  label="Full Name"
                  placeholder="Jane Doe"
                  autoComplete="name"
                  error={errors.full_name?.message}
                  {...register("full_name")}
                />
              </div>
              <div>
                <Input
                  label="Corporate Email"
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
                  placeholder="Minimum 8 characters"
                  autoComplete="new-password"
                  error={errors.password?.message}
                  {...register("password")}
                />
              </div>

              <div className="flex items-center gap-2 pt-1">
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => setStep(1)}
                  disabled={isSubmitting || success}
                  className="px-3"
                >
                  <ArrowLeft className="h-4 w-4" />
                </Button>
                <Button type="submit" className="flex-1" disabled={isSubmitting || success}>
                  {isSubmitting ? "Creating Account..." : "Create Account"}
                </Button>
              </div>

              <div className="pt-2 text-center text-xs text-muted-foreground">
                Already have an account?{" "}
                <Link href="/login" className="font-medium text-primary hover:underline">
                  Sign in
                </Link>
              </div>
            </form>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
