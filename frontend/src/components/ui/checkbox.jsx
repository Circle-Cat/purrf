import * as React from "react";
import * as CheckboxPrimitive from "@radix-ui/react-checkbox";
import { CheckIcon, Minus } from "lucide-react";

import { cn } from "@/lib/utils";

function Checkbox({ className, checked, ...props }) {
  const isIndeterminate = checked === "indeterminate";

  return (
    <CheckboxPrimitive.Root
      data-slot="checkbox"
      data-indeterminate={isIndeterminate ? "" : undefined}
      className={cn(
        "border-input dark:bg-input/30 dark:hover:bg-input/50",
        "focus-visible:border-ring focus-visible:ring-ring/50 focus-visible:ring-3",
        "aria-invalid:ring-destructive/20 dark:aria-invalid:ring-destructive/40 aria-invalid:border-destructive dark:aria-invalid:border-destructive/50 aria-invalid:ring-3",
        "peer size-4 shrink-0 rounded-md border bg-transparent transition-colors outline-none select-none",
        "disabled:cursor-not-allowed disabled:opacity-50",
        "data-checked:bg-primary data-checked:text-primary-foreground data-checked:border-primary",
        "data-[state=indeterminate]:bg-primary data-[state=indeterminate]:text-primary-foreground data-[state=indeterminate]:border-primary",
        className,
      )}
      checked={checked}
      {...props}
    >
      <CheckboxPrimitive.Indicator
        data-slot="checkbox-indicator"
        className={cn(
          "flex items-center justify-center text-current",
          "[&_svg]:pointer-events-none [&_svg]:shrink-0 [&_svg:not([class*='size-'])]:size-3.5",
        )}
      >
        {isIndeterminate ? (
          <Minus className="pointer-events-none" />
        ) : (
          <CheckIcon className="pointer-events-none" />
        )}
      </CheckboxPrimitive.Indicator>
    </CheckboxPrimitive.Root>
  );
}

export { Checkbox };
