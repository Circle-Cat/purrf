import { useEffect, useState } from "react";
import { Loader2 } from "lucide-react";
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
import { Progress } from "@/components/ui/progress";
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
 * @param {(file: File, onProgress: (percent: number) => void) => Promise<Object>} [props.onConfirm]
 *   `onProgress` is handed the whole-number percentage of the archive that
 *   has reached the server. A caller that cannot measure the transfer simply
 *   never calls it, and the dialog falls back to saying nothing more than
 *   that an upload is running.
 */
export default function UploadPackageDialog({
  course,
  open,
  onOpenChange,
  onConfirm,
}) {
  const [file, setFile] = useState(null);
  // null while idle, then which half of the wait we are in: "uploading" is
  // the transfer, "validating" is everything the server does once it holds
  // the whole archive.
  const [phase, setPhase] = useState(null);
  const [percent, setPercent] = useState(null);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);
  const busy = phase !== null;

  useEffect(() => {
    if (open) {
      setFile(null);
      setPhase(null);
      setPercent(null);
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
    setPhase("uploading");
    setPercent(null);
    setError(null);
    try {
      // The last byte arriving is the end of the only stretch anyone can
      // measure. What follows -- unzipping the archive, reading the
      // manifest, storing a couple of hundred files -- reports nothing, and
      // on the packages we ship is the longer half of the two, so the count
      // stops here rather than resting at 100%.
      const data = await onConfirm?.(file, (reached) => {
        setPercent(reached);
        if (reached >= 100) setPhase("validating");
      });
      setResult(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setPhase(null);
    }
  };

  const handleClose = () => onOpenChange?.(false);

  const idleLabel = isReplacing ? "Replace package" : "Upload package";
  const submitLabel =
    { uploading: "Uploading...", validating: "Checking..." }[phase] ??
    idleLabel;

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

            {phase === "uploading" && percent !== null && (
              <div className="space-y-1.5" aria-live="polite">
                <Progress value={percent} />
                <p className="text-xs text-muted-foreground">{percent}%</p>
              </div>
            )}

            {phase === "validating" && (
              <p
                className="flex items-center gap-2 text-sm text-muted-foreground"
                aria-live="polite"
              >
                <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
                Checking package...
              </p>
            )}

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
                {submitLabel}
              </Button>
            </>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
