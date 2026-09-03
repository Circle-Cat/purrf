import { AlertTriangle, HelpCircle, CheckCircle2 } from "lucide-react";

/**
 * Spec §4.2 (static health check box) / §5: the one signal that says what a course
 * needs in order to finish, read from the package itself -- not from what
 * happened at runtime (that's the trial-run panel, §4.3). The same component
 * renders from two data sources: a just-uploaded `TrainingPackageUploadResultDto`
 * or a re-read `TrainingCompletionConfigDto`; both carry the same three
 * fields this box reads.
 *
 * An unreadable package gets its own state rather than staying silent --
 * silence here would read as "nothing wrong", which is the mistake that let
 * the 2026-08-29 course go undetected.
 *
 * @param {Object} props
 * @param {{completionConfigReadable: boolean, completesViaStoryline?: boolean, completionPercentage?: number|null}} props.config
 */
export default function PackageHealthBox({ config }) {
  const { completionConfigReadable, completesViaStoryline, completionPercentage } =
    config;

  if (!completionConfigReadable) {
    return (
      <div className="flex items-start gap-2 rounded-md border border-border bg-muted/40 p-3 text-sm">
        <HelpCircle
          className="mt-0.5 size-4 shrink-0 text-muted-foreground"
          aria-hidden="true"
        />
        <div className="space-y-1">
          <p className="font-medium">
            Completion behaviour could not be determined
          </p>
          <p className="text-muted-foreground">
            This package was not built with a toolchain we can read. The
            trial run is the only check — it will not be assignable until
            someone finishes it.
          </p>
        </div>
      </div>
    );
  }

  if (completesViaStoryline) {
    return (
      <div
        className="flex items-start gap-2 rounded-md border p-3 text-sm"
        style={{ borderColor: "var(--stage-tech)" }}
      >
        <AlertTriangle
          className="mt-0.5 size-4 shrink-0"
          style={{ color: "var(--stage-tech)" }}
          aria-hidden="true"
        />
        <div className="space-y-1">
          <p className="font-medium">
            Completes through an embedded Storyline block
          </p>
          <p className="text-muted-foreground">
            Finishing every Rise lesson will not mark this course complete.
          </p>
          {completionPercentage != null && (
            <p className="text-xs text-muted-foreground">
              threshold {completionPercentage}%
            </p>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="flex items-start gap-2 rounded-md border border-border bg-muted/40 p-3 text-sm">
      <CheckCircle2
        className="mt-0.5 size-4 shrink-0"
        style={{ color: "var(--stage-hired)" }}
        aria-hidden="true"
      />
      <div className="space-y-1">
        <p className="font-medium">Completes on its own reporting</p>
        <p className="text-muted-foreground">
          No embedded block is needed to finish this course.
        </p>
        {completionPercentage != null && (
          <p className="text-xs text-muted-foreground">
            threshold {completionPercentage}%
          </p>
        )}
      </div>
    </div>
  );
}
