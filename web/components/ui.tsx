"use client";

import { useState } from "react";
import type {
  ButtonHTMLAttributes,
  InputHTMLAttributes,
  LabelHTMLAttributes,
  ReactNode,
  SelectHTMLAttributes,
  TextareaHTMLAttributes,
} from "react";

export function Card({
  children,
  className = "",
  hoverable = false,
}: {
  children: ReactNode;
  className?: string;
  hoverable?: boolean;
}) {
  return (
    <div
      className={`rounded-2xl border border-[var(--color-border)] bg-[var(--color-card)] p-6 shadow-sm transition-all duration-200 ${
        hoverable ? "hover:-translate-y-0.5 hover:border-[var(--color-primary)]/30 hover:shadow-lg hover:shadow-blue-900/5" : ""
      } ${className}`}
    >
      {children}
    </div>
  );
}

export function Field({
  label,
  hint,
  error,
  children,
}: {
  label: string;
  hint?: string;
  error?: string;
  children: ReactNode;
}) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-sm font-medium text-[var(--color-text)]">{label}</span>
      {children}
      {error ? (
        <span className="mt-1.5 block text-xs font-medium text-[var(--color-danger)]" role="alert">
          {error}
        </span>
      ) : (
        hint && <span className="mt-1.5 block text-xs text-[var(--color-muted)]">{hint}</span>
      )}
    </label>
  );
}

const fieldClasses =
  "w-full rounded-xl border border-[var(--color-border)] bg-white px-3.5 py-2.5 text-sm text-[var(--color-text)] shadow-sm transition-colors placeholder:text-[var(--color-muted)] focus:border-[var(--color-primary)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]/20 disabled:cursor-not-allowed disabled:bg-slate-50 disabled:text-[var(--color-muted)]";

export function Input(props: InputHTMLAttributes<HTMLInputElement> & { invalid?: boolean }) {
  const { invalid, className = "", ...rest } = props;
  return (
    <input
      {...rest}
      className={`${fieldClasses} ${invalid ? "border-[var(--color-danger)] focus:border-[var(--color-danger)] focus:ring-[var(--color-danger)]/20" : ""} ${className}`}
    />
  );
}

export function PasswordInput(
  props: InputHTMLAttributes<HTMLInputElement> & { invalid?: boolean },
) {
  const [visible, setVisible] = useState(false);
  const { invalid, className = "", ...rest } = props;
  return (
    <div className="relative">
      <input
        {...rest}
        type={visible ? "text" : "password"}
        className={`${fieldClasses} pr-10 ${invalid ? "border-[var(--color-danger)] focus:border-[var(--color-danger)] focus:ring-[var(--color-danger)]/20" : ""} ${className}`}
      />
      <button
        type="button"
        onClick={() => setVisible((v) => !v)}
        aria-label={visible ? "Hide password" : "Show password"}
        className="absolute inset-y-0 right-0 flex items-center px-3 text-[var(--color-muted)] transition-colors hover:text-[var(--color-text)]"
      >
        {visible ? (
          <svg viewBox="0 0 24 24" fill="none" className="h-4 w-4" aria-hidden="true">
            <path
              d="M3 3l18 18M10.6 10.6a2 2 0 0 0 2.8 2.8M9.4 5.5A10.4 10.4 0 0 1 12 5c5 0 9 4 10 7-.3.9-1 2.1-2 3.2M6.2 6.9C4.2 8.1 2.7 9.9 2 12c1 3 5 7 10 7 1.4 0 2.7-.3 3.9-.8"
              stroke="currentColor"
              strokeWidth="1.7"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        ) : (
          <svg viewBox="0 0 24 24" fill="none" className="h-4 w-4" aria-hidden="true">
            <path
              d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7-10-7-10-7Z"
              stroke="currentColor"
              strokeWidth="1.7"
              strokeLinejoin="round"
            />
            <circle cx="12" cy="12" r="3" stroke="currentColor" strokeWidth="1.7" />
          </svg>
        )}
      </button>
    </div>
  );
}

export function Textarea(props: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea {...props} className={`${fieldClasses} resize-y ${props.className ?? ""}`} />;
}

export function Select(props: SelectHTMLAttributes<HTMLSelectElement>) {
  return <select {...props} className={`${fieldClasses} bg-white ${props.className ?? ""}`} />;
}

export function Spinner({ className = "" }: { className?: string }) {
  return (
    <svg
      className={`h-4 w-4 animate-spin ${className}`}
      viewBox="0 0 24 24"
      fill="none"
      aria-hidden="true"
    >
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path
        className="opacity-90"
        fill="currentColor"
        d="M4 12a8 8 0 0 1 8-8V0C5.373 0 0 5.373 0 12h4z"
      />
    </svg>
  );
}

export function Button({
  variant = "primary",
  size = "md",
  className = "",
  loading = false,
  disabled,
  children,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "danger" | "ghost";
  size?: "sm" | "md";
  loading?: boolean;
}) {
  const variants = {
    primary:
      "gradient-primary gradient-primary-hover text-white shadow-sm shadow-blue-900/10 active:scale-[0.98] disabled:bg-slate-300 disabled:bg-none",
    secondary:
      "bg-white text-[var(--color-text)] border border-[var(--color-border)] hover:bg-slate-50 hover:border-slate-300 active:scale-[0.98] disabled:text-[var(--color-muted)]",
    danger:
      "bg-[var(--color-danger)] text-white shadow-sm hover:bg-red-600 active:scale-[0.98] disabled:bg-red-300",
    ghost:
      "bg-transparent text-[var(--color-text)] hover:bg-slate-100 active:scale-[0.98] disabled:text-[var(--color-muted)]",
  };
  const sizes = {
    sm: "px-3 py-1.5 text-xs",
    md: "px-4 py-2.5 text-sm",
  };
  return (
    <button
      {...props}
      disabled={disabled || loading}
      className={`inline-flex items-center justify-center gap-2 rounded-xl font-medium transition-all duration-150 disabled:cursor-not-allowed ${variants[variant]} ${sizes[size]} ${className}`}
    >
      {loading && <Spinner />}
      {children}
    </button>
  );
}

const taintStyles: Record<string, string> = {
  trusted: "bg-green-50 text-green-700 ring-green-200",
  untrusted: "bg-amber-50 text-amber-700 ring-amber-200",
  quarantined: "bg-red-50 text-red-700 ring-red-200",
};

const taintLabels: Record<string, string> = {
  trusted: "trusted",
  untrusted: "untrusted",
  quarantined: "quarantined",
};

const taintDot: Record<string, string> = {
  trusted: "bg-green-500",
  untrusted: "bg-amber-500",
  quarantined: "bg-red-500",
};

export function TaintBadge({ taint }: { taint: string }) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ring-1 ring-inset ${taintStyles[taint] ?? "bg-slate-100 text-slate-700 ring-slate-200"}`}
    >
      <span className={`h-1.5 w-1.5 rounded-full ${taintDot[taint] ?? "bg-slate-400"}`} />
      {taintLabels[taint] ?? taint}
    </span>
  );
}

export function OutcomeBadge({ outcome }: { outcome: string }) {
  const styles: Record<string, string> = {
    allow: "bg-green-50 text-green-700 ring-green-200",
    deny: "bg-red-50 text-red-700 ring-red-200",
    gated: "bg-amber-50 text-amber-700 ring-amber-200",
  };
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-1 text-xs font-medium ring-1 ring-inset ${styles[outcome] ?? "bg-slate-100 text-slate-700 ring-slate-200"}`}
    >
      {outcome}
    </span>
  );
}

export function Chip({
  active = false,
  onClick,
  children,
}: {
  active?: boolean;
  onClick?: () => void;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`inline-flex items-center gap-1 rounded-full border px-3 py-1 text-xs font-medium transition-colors ${
        active
          ? "border-[var(--color-primary)]/40 bg-blue-50 text-[var(--color-primary)]"
          : "border-[var(--color-border)] bg-white text-[var(--color-muted)] hover:border-[var(--color-accent)]/50 hover:text-[var(--color-text)]"
      }`}
    >
      {children}
    </button>
  );
}

export function EmptyState({ children }: { children: ReactNode }) {
  return (
    <div className="animate-fade-in rounded-2xl border border-dashed border-[var(--color-border)] px-4 py-12 text-center text-sm text-[var(--color-muted)]">
      {children}
    </div>
  );
}

export function ErrorBanner({ children }: { children: ReactNode }) {
  return (
    <div
      role="alert"
      className="animate-slide-up rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700"
    >
      {children}
    </div>
  );
}

export function SuccessBanner({ children }: { children: ReactNode }) {
  return (
    <div className="animate-slide-up rounded-xl border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-700">
      {children}
    </div>
  );
}

export function Label(props: LabelHTMLAttributes<HTMLLabelElement>) {
  return (
    <label {...props} className={`text-sm font-medium text-[var(--color-text)] ${props.className ?? ""}`} />
  );
}

export function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`skeleton rounded-lg ${className}`} />;
}

export function Pagination({
  page,
  pageCount,
  onChange,
}: {
  page: number;
  pageCount: number;
  onChange: (page: number) => void;
}) {
  if (pageCount <= 1) return null;
  return (
    <div className="flex items-center justify-between gap-4 px-1 py-1 text-sm text-[var(--color-muted)]">
      <span>
        Page {page + 1} of {pageCount}
      </span>
      <div className="flex items-center gap-2">
        <Button
          variant="secondary"
          size="sm"
          disabled={page === 0}
          onClick={() => onChange(page - 1)}
          aria-label="Previous page"
        >
          Previous
        </Button>
        <Button
          variant="secondary"
          size="sm"
          disabled={page >= pageCount - 1}
          onClick={() => onChange(page + 1)}
          aria-label="Next page"
        >
          Next
        </Button>
      </div>
    </div>
  );
}

export function PageHeader({ title, description }: { title: string; description?: ReactNode }) {
  return (
    <div className="animate-slide-up">
      <h1 className="gradient-accent-text text-2xl font-semibold tracking-tight">{title}</h1>
      {description && <p className="mt-2 max-w-3xl text-sm leading-relaxed text-[var(--color-muted)]">{description}</p>}
    </div>
  );
}
