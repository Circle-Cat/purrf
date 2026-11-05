import * as React from "react";

import { cn } from "@/lib/utils";

function Input({ className, type = "text", ...props }) {
  return (
    <input
      type={type}
      data-slot="input"
      className={cn(
        "border-input placeholder:text-muted-foreground dark:bg-input/30 dark:hover:bg-input/50",
        "focus-visible:border-ring focus-visible:ring-ring/50 focus-visible:ring-3",
        "aria-invalid:ring-destructive/20 dark:aria-invalid:ring-destructive/40 aria-invalid:border-destructive dark:aria-invalid:border-destructive/50 aria-invalid:ring-3",
        "flex h-8 w-full rounded-lg border bg-transparent px-3 py-1 text-sm transition-colors outline-none",
        "disabled:cursor-not-allowed disabled:opacity-50",
        className,
      )}
      {...props}
    />
  );
}

export { Input };
