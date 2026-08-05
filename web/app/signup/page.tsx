"use client";

import Link from "next/link";
import { useState } from "react";

import { Button, Card, ErrorBanner, Field, Input, PasswordInput } from "@/components/ui";

interface FormState {
  fullName: string;
  email: string;
  company: string;
  password: string;
  confirmPassword: string;
}

interface FormErrors {
  fullName?: string;
  email?: string;
  password?: string;
  confirmPassword?: string;
}

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

function validate(form: FormState): FormErrors {
  const errors: FormErrors = {};
  if (!form.fullName.trim()) errors.fullName = "Full name is required.";
  if (!form.email.trim()) {
    errors.email = "Email is required.";
  } else if (!EMAIL_RE.test(form.email)) {
    errors.email = "Enter a valid email address.";
  }
  if (!form.password) {
    errors.password = "Password is required.";
  } else if (form.password.length < 8) {
    errors.password = "Password must be at least 8 characters.";
  }
  if (!form.confirmPassword) {
    errors.confirmPassword = "Please confirm your password.";
  } else if (form.confirmPassword !== form.password) {
    errors.confirmPassword = "Passwords do not match.";
  }
  return errors;
}

export default function SignUpPage() {
  const [form, setForm] = useState<FormState>({
    fullName: "",
    email: "",
    company: "",
    password: "",
    confirmPassword: "",
  });
  const [errors, setErrors] = useState<FormErrors>({});
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  function update<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const nextErrors = validate(form);
    setErrors(nextErrors);
    setSubmitError(null);
    if (Object.keys(nextErrors).length > 0) return;

    setIsSubmitting(true);
    try {
      // TODO(auth): wire this up to a real account-creation endpoint once the
      // backend exposes one. GovernedMemory's REST API (api/main.py) is
      // currently tenant-API-key based and has no user signup/auth routes --
      // this form is UI-only until that lands.
      await new Promise((resolve) => setTimeout(resolve, 900));
      setSuccess(true);
    } catch {
      setSubmitError("Something went wrong creating your account. Please try again.");
    } finally {
      setIsSubmitting(false);
    }
  }

  if (success) {
    return (
      <div className="mx-auto flex max-w-md flex-col items-center gap-4 py-16 text-center animate-scale-in">
        <span className="flex h-14 w-14 items-center justify-center rounded-full bg-green-50 text-green-600">
          <svg viewBox="0 0 24 24" fill="none" className="h-7 w-7" aria-hidden="true">
            <path
              d="M5 13l4 4L19 7"
              stroke="currentColor"
              strokeWidth="2.2"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </span>
        <h1 className="text-xl font-semibold text-[var(--color-text)]">Account created</h1>
        <p className="text-sm text-[var(--color-muted)]">
          Welcome, {form.fullName.split(" ")[0] || "there"} — your account request has been received.
        </p>
        <Link href="/write">
          <Button variant="secondary">Go to console</Button>
        </Link>
      </div>
    );
  }

  return (
    <div className="mx-auto flex max-w-md flex-col gap-6 py-10 animate-slide-up">
      <div className="text-center">
        <h1 className="text-2xl font-semibold tracking-tight text-[var(--color-text)]">Create your account</h1>
        <p className="mt-2 text-sm text-[var(--color-muted)]">
          Get started with Governed Memory in a few seconds.
        </p>
      </div>

      <Card>
        <form className="space-y-4" onSubmit={handleSubmit} noValidate>
          <Field label="Full name" error={errors.fullName}>
            <Input
              autoComplete="name"
              placeholder="Jane Doe"
              value={form.fullName}
              invalid={!!errors.fullName}
              onChange={(e) => update("fullName", e.target.value)}
            />
          </Field>

          <Field label="Email" error={errors.email}>
            <Input
              type="email"
              autoComplete="email"
              placeholder="jane@company.com"
              value={form.email}
              invalid={!!errors.email}
              onChange={(e) => update("email", e.target.value)}
            />
          </Field>

          <Field label="Company (optional)">
            <Input
              autoComplete="organization"
              placeholder="Acme Inc."
              value={form.company}
              onChange={(e) => update("company", e.target.value)}
            />
          </Field>

          <Field label="Password" error={errors.password} hint={!errors.password ? "At least 8 characters." : undefined}>
            <PasswordInput
              autoComplete="new-password"
              placeholder="••••••••"
              value={form.password}
              invalid={!!errors.password}
              onChange={(e) => update("password", e.target.value)}
            />
          </Field>

          <Field label="Confirm password" error={errors.confirmPassword}>
            <PasswordInput
              autoComplete="new-password"
              placeholder="••••••••"
              value={form.confirmPassword}
              invalid={!!errors.confirmPassword}
              onChange={(e) => update("confirmPassword", e.target.value)}
            />
          </Field>

          {submitError && <ErrorBanner>{submitError}</ErrorBanner>}

          <Button type="submit" className="w-full" loading={isSubmitting} disabled={isSubmitting}>
            {isSubmitting ? "Creating account…" : "Create Account"}
          </Button>

          <p className="text-center text-sm text-[var(--color-muted)]">
            Already have an account?{" "}
            <Link href="/write" className="font-medium text-[var(--color-primary)] hover:underline">
              Sign In
            </Link>
          </p>
        </form>
      </Card>
    </div>
  );
}
