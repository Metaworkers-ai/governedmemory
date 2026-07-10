import type { ButtonHTMLAttributes, InputHTMLAttributes, LabelHTMLAttributes, ReactNode, SelectHTMLAttributes, TextareaHTMLAttributes } from "react";

export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <div className={`rounded-lg border border-neutral-200 bg-white p-5 shadow-sm ${className}`}>
      {children}
    </div>
  );
}

export function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: ReactNode;
}) {
  return (
    <label className="block">
      <span className="mb-1 block text-sm font-medium text-neutral-700">{label}</span>
      {children}
      {hint && <span className="mt-1 block text-xs text-neutral-500">{hint}</span>}
    </label>
  );
}

const fieldClasses =
  "w-full rounded-md border border-neutral-300 px-3 py-2 text-sm text-neutral-900 shadow-sm focus:border-neutral-500 focus:outline-none focus:ring-1 focus:ring-neutral-500";

export function Input(props: InputHTMLAttributes<HTMLInputElement>) {
  return <input {...props} className={`${fieldClasses} ${props.className ?? ""}`} />;
}

export function Textarea(props: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea {...props} className={`${fieldClasses} ${props.className ?? ""}`} />;
}

export function Select(props: SelectHTMLAttributes<HTMLSelectElement>) {
  return <select {...props} className={`${fieldClasses} bg-white ${props.className ?? ""}`} />;
}

export function Button({
  variant = "primary",
  className = "",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "secondary" | "danger" }) {
  const variants = {
    primary: "bg-neutral-900 text-white hover:bg-neutral-700 disabled:bg-neutral-300",
    secondary:
      "bg-white text-neutral-700 border border-neutral-300 hover:bg-neutral-50 disabled:text-neutral-400",
    danger: "bg-red-600 text-white hover:bg-red-700 disabled:bg-red-300",
  };
  return (
    <button
      {...props}
      className={`rounded-md px-3.5 py-2 text-sm font-medium transition-colors disabled:cursor-not-allowed ${variants[variant]} ${className}`}
    />
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

export function TaintBadge({ taint }: { taint: string }) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset ${taintStyles[taint] ?? "bg-neutral-100 text-neutral-700 ring-neutral-200"}`}
    >
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
      className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset ${styles[outcome] ?? "bg-neutral-100 text-neutral-700 ring-neutral-200"}`}
    >
      {outcome}
    </span>
  );
}

export function EmptyState({ children }: { children: ReactNode }) {
  return (
    <div className="rounded-lg border border-dashed border-neutral-300 px-4 py-8 text-center text-sm text-neutral-500">
      {children}
    </div>
  );
}

export function ErrorBanner({ children }: { children: ReactNode }) {
  return (
    <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
      {children}
    </div>
  );
}

export function SuccessBanner({ children }: { children: ReactNode }) {
  return (
    <div className="rounded-md border border-green-200 bg-green-50 px-3 py-2 text-sm text-green-700">
      {children}
    </div>
  );
}

export function Label(props: LabelHTMLAttributes<HTMLLabelElement>) {
  return <label {...props} className={`text-sm font-medium text-neutral-700 ${props.className ?? ""}`} />;
}
