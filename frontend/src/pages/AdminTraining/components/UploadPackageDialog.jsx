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
import PackageHealthBox from "@/pages/AdminTraining/components/PackageHealthBox";

/**
 * Upload or replace a course's SCORM package. Spec §4.2.
 *
 * Presentational, matching `DeactivateDialog`: it owns only its own busy
 * state, the picked `File`, and the result of the last attempt. The caller
 * (`CourseTable`) owns the mutation -- `onConfirm(file)` is expected to call
 * `uploadPackage` and resolve with the `TrainingPackageUploadResultDto`, or
 * reject with an `Error` whose `message` is the backend's rejection text.
 * That message is shown as-is; it is written to be forwarded to whoever
 * exported the course, so this dialog must never paraphrase it.
 *
 * A successful upload renders `PackageHealthBox` straight from the response
 * -- no follow-up `GET` -- and swaps the footer to a single "Done" that
 * closes the dialog.
 *
 * @param {Object} props
 * @param {{courseId: number, packageUploadedAt?: string|null, packageVersion?: string|null, assignedCount: number, unfinishedCount: number}} props.course
 *   `packageUploadedAt` is what makes this a replacement; `packageVersion` is
 *   only the name to call the outgoing package by, and plenty of packages do
 *   not tell us one.
 * @param {boolean} props.open
 * @param {(open: boolean) => void} [props.onOpenChange]
 * @param {(file: File) => Promise<Object>} [props.onConfirm]
 */
export default function UploadPackageDialog({
  course,
  open,
  onOpenChange,
  onConfirm,
}) {
  const [file, setFile] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);

  useEffect(() => {
    if (open) {
      setFile(null);
      setBusy(false);
      setError(null);
      setResult(null);
    }
  }, [open]);

  // Whether a package is there to be replaced, not whether we could read its
  // version. An export we cannot read -- Captivate, iSpring, bare Storyline
  // -- carries no version at all, and replacing that one costs its learners
  // exactly what replacing any other does.
  const isReplacing = Boolean(course.packageUploadedAt);
  const completedCount = course.assignedCount - course.unfinishedCount;

  const handleSubmit = async () => {
    if (!file) return;
    setBusy(true);
    setError(null);
    try {
      const data = await onConfirm?.(file);
      setResult(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  const handleClose = () => onOpenChange?.(false);

  return (
    <Dialog open={open} onOpenChange={(next) => !next && handleClose()}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>
            {isReplacing ? "Replace package" : "Upload package"}
          </DialogTitle>
          <DialogDescription>
            {isReplacing
              ? "Replacing the package clears verification and resets in-progress learners."
              : "Choose a SCORM 1.2 package (.zip) to upload for this course."}
          </DialogDescription>
        </DialogHeader>

        {result ? (
          <div className="space-y-3">
            <p className="text-sm font-medium">Package uploaded.</p>
            <PackageHealthBox config={result} />
          </div>
        ) : (
          <div className="space-y-4">
            {isReplacing && (
              <div
                className="space-y-1.5 rounded-md border p-3 text-sm"
                style={{ borderColor: "var(--stage-tech)" }}
              >
                <p className="font-medium">
                  {course.packageVersion
                    ? `This replaces package ${course.packageVersion}`
                    : "This replaces the current package"}
                </p>
                <p className="text-muted-foreground">
                  Verification is cleared — the course must be run to completion
                  again before anyone can be assigned.
                </p>
                <p className="text-muted-foreground">
                  {course.unfinishedCount} learners in progress will restart
                  from the beginning. {completedCount} completed records are
                  untouched.
                </p>
              </div>
            )}

            <div className="space-y-2">
              <Label htmlFor="package-file">SCORM package (.zip)</Label>
              <Input
                id="package-file"
                type="file"
                accept=".zip"
                disabled={busy}
                onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              />
            </div>

            {error && (
              <div className="space-y-1 rounded-md border border-destructive/40 bg-destructive/5 p-3 text-sm text-destructive">
                <p>{error}</p>
                <p className="text-xs text-muted-foreground">
                  Nothing was uploaded. The current package is unchanged.
                </p>
              </div>
            )}
          </div>
        )}

        <DialogFooter>
          {result ? (
            <Button onClick={handleClose}>Done</Button>
          ) : (
            <>
              <Button variant="outline" onClick={handleClose} disabled={busy}>
                Cancel
              </Button>
              <Button onClick={handleSubmit} disabled={busy || !file}>
                {busy
                  ? "Uploading..."
                  : isReplacing
                    ? "Replace package"
                    : "Upload package"}
              </Button>
            </>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
