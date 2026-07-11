import * as React from "react";
import * as CheckboxPrimitive from "@radix-ui/react-checkbox";
import { CheckIcon } from "lucide-react";

import { cn } from "@/lib/utils";

function Checkbox({ className, ...props }) {
  return (
    <CheckboxPrimitive.Root
      data-slot="checkbox"
      className={cn(
        "border-input dark:bg-input/30 dark:hover:bg-input/50",
        "focus-visible:border-ring focus-visible:ring-ring/50 focus-visible:ring-3",
        "aria-invalid:ring-destructive/20 dark:aria-invalid:ring-destructive/40 aria-invalid:border-destructive dark:aria-invalid:border-destructive/50 aria-invalid:ring-3",
        "peer size-4 shrink-0 rounded-md border bg-transparent transition-colors outline-none select-none",
        "disabled:cursor-not-allowed disabled:opacity-50",
        "data-checked:bg-primary data-checked:text-primary-foreground data-checked:border-primary",
        className,
      )}
      {...props}
    >
      <CheckboxPrimitive.Indicator
        data-slot="checkbox-indicator"
        className={cn(
          "flex items-center justify-center text-current",
          "[&_svg]:pointer-events-none [&_svg]:shrink-0 [&_svg:not([class*='size-'])]:size-3.5",
        )}
      >
        <CheckIcon className="pointer-events-none" />
      </CheckboxPrimitive.Indicator>
    </CheckboxPrimitive.Root>
  );
}

export { Checkbox };
