import { useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";

/**
 * Confirms publishing a course's staged package. Spec §6.3: publishing puts
 * the package in front of learners and deletes the outgoing one, and it
 * clears everyone's progress on the course -- this dialog is the one place
 * an admin is told what that costs before it happens.
 *
 * Presentational only, matching `DeactivateDialog`: it tracks its own busy
 * state and nothing else. The caller owns the mutation, and is responsible
 * for closing the dialog and refreshing on success and for reporting
 * failure -- this dialog never calls the API itself.
 *
 * The restart count is `unfinishedCount`, not the publish result's own
 * `learnersReset` -- that field counts finished rows too and is a different,
 * larger number than what this dialog is warning about.
 *
 * @param {Object} props
 * @param {{courseId: number, liveState: string, packageVersion?: string|null, assignedCount: number, unfinishedCount: number, staged: {packageVersion?: string|null}}} props.course
 *   `packageVersion` names the outgoing package, `staged.packageVersion` the
 *   one replacing it -- both nullable, for a package built by a toolchain we
 *   cannot read.
 * @param {boolean} props.open
 * @param {(open: boolean) => void} [props.onOpenChange]
 * @param {() => Promise<void>} props.onConfirm - publishes the staged package.
 */
export default function PublishDialog({
  course,
  open,
  onOpenChange,
  onConfirm,
}) {
  const [busy, setBusy] = useState(false);

  const handleConfirm = async () => {
    setBusy(true);
    try {
      await onConfirm();
    } finally {
      setBusy(false);
    }
  };

  const { staged, packageVersion, liveState, unfinishedCount, assignedCount } =
    course;
  const isLive = liveState === "live";
  const completedCount = assignedCount - unfinishedCount;
  // Same nullability as `StagedRow` and `UploadPackageDialog`: a package
  // built by a toolchain we cannot read carries no version, so name the
  // thing without one instead of leaving a gap in the sentence.
  const stagedName = staged.packageVersion ?? "the staged package";
  const currentName = packageVersion ?? "the current package";

  return (
    <Dialog open={open} onOpenChange={(next) => !next && onOpenChange?.(false)}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Publish package</DialogTitle>
          <DialogDescription>
            {isLive
              ? `${stagedName} replaces ${currentName} for everyone on this course.`
              : `${stagedName} becomes the package this course serves.`}
          </DialogDescription>
        </DialogHeader>
        {/* All three consequences are consequences of a replacement. With
            nothing live, nobody has the course open, nobody is part-way
            through it and there is no outgoing package -- the description
            above is then the whole truth, so the box does not render. */}
        {isLive && (
          <div className="space-y-1.5 rounded-md border p-3 text-sm text-muted-foreground">
            <p>
              {unfinishedCount} learners in progress will restart from the
              beginning. {completedCount} completed records are untouched.
            </p>
            <p>
              Anyone with the course open right now will see it stop loading
              until they reload.
            </p>
            <p>{currentName} is deleted and cannot be brought back.</p>
          </div>
        )}
        <DialogFooter>
          <Button
            variant="outline"
            onClick={() => onOpenChange?.(false)}
            disabled={busy}
          >
            Cancel
          </Button>
          <Button onClick={handleConfirm} disabled={busy}>
            {busy ? "Publishing..." : "Publish package"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
