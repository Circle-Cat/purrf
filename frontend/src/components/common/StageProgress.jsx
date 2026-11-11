import { Check, X } from "lucide-react";

import { cn } from "@/lib/utils";

const STATE_TEXT = {
  done: "done",
  failed: "missed",
  current: "current step",
};

const CURRENT_TONE = {
  normal: {
    ring: "border-[#6035F3]",
    dot: "bg-[#6035F3]",
    label: "text-purple-900",
  },
  amber: {
    ring: "border-amber-700",
    dot: "bg-amber-700",
    label: "text-amber-800",
  },
  muted: {
    ring: "border-slate-400",
    dot: "bg-slate-400",
    label: "text-slate-600",
  },
};

function StepDot({ state, tone }) {
  const base =
    "relative z-10 flex size-5 items-center justify-center rounded-full";
  if (state === "done") {
    return (
      <span className={cn(base, "bg-[#6035F3] text-white")}>
        <Check className="size-3" strokeWidth={3.5} aria-hidden="true" />
      </span>
    );
  }
  if (state === "failed") {
    return (
      <span className={cn(base, "bg-slate-400 text-white")}>
        <X className="size-3" strokeWidth={3.5} aria-hidden="true" />
      </span>
    );
  }
  if (state === "current") {
    const colors = CURRENT_TONE[tone] ?? CURRENT_TONE.normal;
    return (
      <span className={cn(base, "border-2 bg-white", colors.ring)}>
        <span className={cn("size-2 rounded-full", colors.dot)} />
      </span>
    );
  }
  return <span className={cn(base, "border-2 border-slate-300 bg-white")} />;
}

/**
 * A horizontal progress bar over a program's steps. Each program shows its
 * own bar inside its own section.
 *
 * Steps are an ordered list; the current step carries aria-current="step"
 * and done or missed steps say so in visually hidden text, so colour is
 * never the only signal. Below the `sm` breakpoint the bar collapses to a
 * "‹step› · step N of M" line over a thin progress track.
 *
 * @param {Object} props
 * @param {Array<{key: string, label: string, state: "done"|"current"|"failed"|"upcoming"}>} props.steps -
 *   The steps in order.
 * @param {"normal"|"amber"|"muted"} [props.tone="normal"] - Colour of the
 *   current step.
 * @param {string} props.label - Accessible name of the list.
 * @param {(label: string, index: number, total: number) => string} props.narrowText -
 *   Builds the narrow-screen line.
 * @returns {JSX.Element}
 */
export default function StageProgress({
  steps,
  tone = "normal",
  label,
  narrowText,
}) {
  const focusIndex = Math.max(
    steps.findIndex((s) => s.state === "current"),
    steps.findIndex((s) => s.state === "failed"),
  );
  const focusStep = steps[focusIndex] ?? steps[0];
  const doneCount = steps.filter((s) => s.state === "done").length;
  const colors = CURRENT_TONE[tone] ?? CURRENT_TONE.normal;

  return (
    <div>
      <ol
        aria-label={label}
        className="m-0 hidden max-w-md list-none p-0 sm:grid"
        style={{
          gridTemplateColumns: `repeat(${steps.length}, minmax(0, 1fr))`,
        }}
      >
        {steps.map((step, i) => {
          const isCurrent = step.state === "current";
          const stateText = STATE_TEXT[step.state];
          return (
            <li
              key={step.key}
              aria-current={isCurrent ? "step" : undefined}
              className="relative flex flex-col items-center gap-2"
            >
              {i > 0 && (
                <span
                  aria-hidden="true"
                  className={cn(
                    "absolute right-1/2 top-2.5 h-0.5 w-full -translate-y-1/2",
                    steps[i - 1].state === "done"
                      ? "bg-[#6035F3]"
                      : "bg-slate-200",
                  )}
                />
              )}
              <StepDot state={step.state} tone={tone} />
              <span
                className={cn(
                  "text-sm",
                  step.state === "done" && "text-slate-700",
                  step.state === "upcoming" && "text-slate-500",
                  step.state === "failed" && "text-slate-500 line-through",
                  isCurrent && cn("font-semibold", colors.label),
                )}
              >
                {step.label}
                {stateText && <span className="sr-only"> ({stateText})</span>}
              </span>
            </li>
          );
        })}
      </ol>

      <div className="sm:hidden">
        <p
          className={cn(
            "m-0 text-sm font-semibold",
            focusStep?.state === "current" ? colors.label : "text-slate-600",
          )}
        >
          {narrowText(focusStep.label, focusIndex + 1 || 1, steps.length)}
        </p>
        <div
          aria-hidden="true"
          className="mt-2 h-1 w-full overflow-hidden rounded-full bg-slate-200"
        >
          <div
            className="h-full rounded-full bg-[#6035F3]"
            style={{ width: `${(doneCount / steps.length) * 100}%` }}
          />
        </div>
      </div>
    </div>
  );
}
