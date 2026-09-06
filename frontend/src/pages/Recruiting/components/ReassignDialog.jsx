import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";

/**
 * Hand a block request you raised to a different reviewer.
 *
 * Reassignment is done by the raiser, not by the reviewer: this is redirecting
 * a question you asked, not handing off a duty you were given. The dropdown
 * therefore excludes the reviewer who currently holds it, not yourself.
 *
 * @param {object} props
 * @param {boolean} props.open Whether the dialog is showing.
 * @param {(open: boolean) => void} props.onOpenChange Close handler.
 * @param {number} props.currentReviewerId The reviewer who holds it now.
 * @param {number} props.currentUserId The raiser. The backend refuses a
 *   request whose reviewer is the person who raised it.
 * @param {number} props.targetUserId The person the request is about. The
 *   backend refuses to send a request to its own target -- they would read
 *   their own sanction and could approve it.
 * @param {{userId: number, name: string}[]} props.holders Pickable reviewers.
 * @param {(reviewerId: number) => void} props.onConfirm Submit handler.
 * @param {boolean} props.submitting Disables the controls while in flight.
 */
const ReassignDialog = ({
  open,
  onOpenChange,
  currentReviewerId,
  currentUserId,
  targetUserId,
  holders = [],
  onConfirm,
  submitting = false,
}) => {
  const [reviewerId, setReviewerId] = useState("");

  useEffect(() => {
    if (open) setReviewerId("");
  }, [open]);

  // Every id the backend's _validate_reviewer refuses, so a pickable option is
  // always a legal one: the reviewer who has it, the raiser, and the target.
  const excluded = new Set(
    [currentReviewerId, currentUserId, targetUserId].filter((id) => id != null),
  );
  const options = holders.filter((h) => !excluded.has(h.userId));

  const submit = () => {
    if (!reviewerId || submitting) return;
    onConfirm(Number(reviewerId));
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Reassign this block request</DialogTitle>
        </DialogHeader>
        <p className="text-sm text-slate-700">
          The request stays open and nothing about it changes except who decides
          it. Both the old and the new reviewer are told.
        </p>
        <div className="space-y-1">
          <Label htmlFor="reassign-reviewer">Reviewer</Label>
          <p className="text-xs text-slate-500">
            The reviewer who has it now, you, and the person this is about are
            all left out of this list.
          </p>
          <select
            id="reassign-reviewer"
            className="w-full rounded-md border border-slate-300 p-2 text-sm"
            value={reviewerId}
            onChange={(e) => setReviewerId(e.target.value)}
          >
            <option value="">Select a reviewer…</option>
            {options.map((h) => (
              <option key={h.userId} value={h.userId}>
                {h.name}
              </option>
            ))}
          </select>
        </div>
        <DialogFooter>
          <Button
            variant="outline"
            onClick={() => onOpenChange(false)}
            disabled={submitting}
          >
            Cancel
          </Button>
          <Button onClick={submit} disabled={!reviewerId || submitting}>
            Reassign
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export default ReassignDialog;
