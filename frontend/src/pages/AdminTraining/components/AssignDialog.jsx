// Deployment-order note (spec §4.4/§7.2): migration c82e1d48e253 made
// `training.deadline` nullable on main, so an assignment sent with no
// deadline works here. Production has not run that migration yet, so the
// same request fails there with a NOT NULL violation until it does. That is
// a deploy-ordering fact, not a defect in this dialog.
import { useEffect, useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { assignCourse } from "@/api/trainingApi";

/**
 * Assign a verified course to one person. Spec §4.4.
 *
 * `Person` is a plain numeric user id, not a name/email search. The obvious
 * existing person list (`/admin/users`) requires `ADMIN_*` permissions,
 * while a training administrator only holds `TRAINING_ADMIN_WRITE` --
 * reusing it would silently demand a second grant. Which search surface to
 * build here is not decided yet, so the dialog says that plainly instead of
 * leaving the field unexplained.
 *
 * Presentational, matching `DeactivateDialog` and `UploadPackageDialog`: it
 * owns only its own form state and busy flag. Unlike those two, `onConfirm`
 * defaults to the real `assignCourse` call so the dialog is usable on its
 * own; `CourseTable` passes its own `onConfirm` to also close the dialog and
 * refetch the course list on success.
 *
 * @param {Object} props
 * @param {{courseId: number, assignedCount: number}} props.course
 * @param {boolean} props.open
 * @param {(open: boolean) => void} [props.onOpenChange]
 * @param {(payload: {userId: number, courseId: number, deadline?: string}) => Promise<Object>} [props.onConfirm]
 */
export default function AssignDialog({
  course,
  open,
  onOpenChange,
  onConfirm = assignCourse,
}) {
  const [personId, setPersonId] = useState("");
  const [deadline, setDeadline] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (open) {
      setPersonId("");
      setDeadline("");
      setBusy(false);
      setError(null);
    }
  }, [open]);

  const handleClose = () => onOpenChange?.(false);

  const canSubmit = personId.trim() !== "" && !Number.isNaN(Number(personId));

  const handleSubmit = async () => {
    if (!canSubmit) return;
    setBusy(true);
    setError(null);
    const payload = { userId: Number(personId), courseId: course.courseId };
    if (deadline) payload.deadline = deadline;
    try {
      await onConfirm(payload);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={(next) => !next && handleClose()}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Assign course</DialogTitle>
          <DialogDescription>
            Already assigned to {course.assignedCount} people. Assigning
            someone a second time does nothing.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor="assign-person">Person (user ID)</Label>
            <Input
              id="assign-person"
              type="number"
              min="1"
              placeholder="e.g. 42"
              disabled={busy}
              value={personId}
              onChange={(e) => setPersonId(e.target.value)}
            />
            <p className="text-xs text-muted-foreground">
              Search by name or email is not built yet -- enter the person's
              user ID directly.
            </p>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="assign-due-date">Due date</Label>
            <Input
              id="assign-due-date"
              type="date"
              disabled={busy}
              value={deadline}
              onChange={(e) => setDeadline(e.target.value)}
            />
            <p className="text-xs text-muted-foreground">
              Leave empty if there is no deadline yet. One can be set later.
            </p>
          </div>

          {error && <p className="text-sm text-destructive">{error}</p>}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={handleClose} disabled={busy}>
            Cancel
          </Button>
          <Button onClick={handleSubmit} disabled={busy || !canSubmit}>
            {busy ? "Assigning..." : "Assign"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
