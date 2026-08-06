import * as React from "react";
import { cn } from "@/lib/utils";

export const Input = React.forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(
  ({ className, ...props }, ref) => (
    <input
      ref={ref}
      className={cn(
        "h-9 w-full rounded-lg border border-border bg-bg-elevated px-3 text-sm text-ink placeholder:text-ink-faint focus-ring",
        className
      )}
      {...props}
    />
  )
);
Input.displayName = "Input";
