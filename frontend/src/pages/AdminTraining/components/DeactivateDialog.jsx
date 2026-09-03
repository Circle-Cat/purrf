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
 * Confirms turning a course off. Spec §4.1: deactivating only blocks new
 * assignments, so this isn't an "are you sure" -- it counts who the change
 * actually reaches, because everyone already assigned keeps their access.
 *
 * Presentational only, matching `StepUpConfirmDialog`: it tracks its own
 * busy state and nothing else. The caller owns the mutation, and is
 * responsible for closing the dialog and refreshing on success and for
 * reporting failure -- this dialog never calls the API itself.
 *
 * @param {Object} props
 * @param {{courseId: number, name?: string, assignedCount: number, unfinishedCount: number}} props.course
 * @param {boolean} props.open
 * @param {(open: boolean) => void} [props.onOpenChange]
 * @param {() => Promise<void>} props.onConfirm - turns the course off.
 */
export default function DeactivateDialog({
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

  return (
    <Dialog open={open} onOpenChange={(next) => !next && onOpenChange?.(false)}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>
            {course.name ? `Turn off ${course.name}` : "Turn off this course"}
          </DialogTitle>
          <DialogDescription>
            This course can no longer be assigned to anyone new.
          </DialogDescription>
        </DialogHeader>
        <p className="text-sm text-muted-foreground">
          The {course.assignedCount} people already assigned keep their
          access and their progress. {course.unfinishedCount} of them have
          not finished yet.
        </p>
        <p className="text-sm text-muted-foreground">
          You can turn it back on at any time. Nothing is deleted.
        </p>
        <DialogFooter>
          <Button
            variant="outline"
            onClick={() => onOpenChange?.(false)}
            disabled={busy}
          >
            Cancel
          </Button>
          <Button
            variant="destructive"
            onClick={handleConfirm}
            disabled={busy}
          >
            {busy ? "Turning off..." : "Turn off course"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
