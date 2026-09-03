import { useState } from "react";
import { toast } from "sonner";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { updateCourse } from "@/api/trainingApi";

/**
 * Confirms turning a course off. Spec §4.1: deactivating only blocks new
 * assignments, so this isn't an "are you sure" -- it counts who the change
 * actually reaches, because everyone already assigned keeps their access.
 *
 * @param {Object} props
 * @param {{courseId: number, name?: string, assignedCount: number, unfinishedCount: number}} props.course
 * @param {boolean} props.open
 * @param {(open: boolean) => void} [props.onOpenChange]
 * @param {() => (void|Promise<void>)} [props.onDeactivated] - called once the course is turned off.
 */
export default function DeactivateDialog({
  course,
  open,
  onOpenChange,
  onDeactivated,
}) {
  const [busy, setBusy] = useState(false);

  const handleDeactivate = async () => {
    setBusy(true);
    try {
      await updateCourse(course.courseId, { isActive: false });
      onOpenChange?.(false);
      await onDeactivated?.();
    } catch (error) {
      toast.error(error.message);
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
            onClick={handleDeactivate}
            disabled={busy}
          >
            {busy ? "Turning off..." : "Turn off course"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
