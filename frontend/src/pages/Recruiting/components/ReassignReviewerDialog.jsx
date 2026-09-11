import { useEffect, useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import EmptyState from "@/pages/Recruiting/components/EmptyState";

/**
 * Move a posting's open review to a different approver.
 *
 * Done by the submitter, not by the reviewer: this is redirecting a question
 * you asked, not handing off a duty you were given. It exists because a
 * reviewer whose account is later deactivated or blocked cannot decide the
 * review and nobody else may, which would otherwise leave the posting in its
 * gate for good.
 *
 * Separate from the block-request ReassignDialog rather than a shared one:
 * that dialog excludes a third person (the request's target), says both
 * reviewers are told, and names a different thing throughout. Only the shape
 * is the same.
 *
 * @param {object} props
 * @param {boolean} props.open Whether the dialog is showing.
 * @param {{userId: number, name: string, email: string}[]} props.approvers
 *   Active posting approvers, already filtered of deactivated and blocked
 *   accounts by the backend's list_active_approvers.
 * @param {number} props.currentUserId The submitter, who cannot review their
 *   own posting.
 * @param {number} props.currentReviewerId The reviewer it is being moved off.
 * @param {boolean} [props.submitting] Disables the controls while in flight.
 * @param {(reviewerId: number) => void} props.onSubmit Submit handler.
 * @param {(open: boolean) => void} props.onOpenChange Close handler.
 */
const ReassignReviewerDialog = ({
  open,
  approvers,
  currentUserId,
  currentReviewerId,
  submitting = false,
  onSubmit,
  onOpenChange,
}) => {
  const [reviewerId, setReviewerId] = useState("");

  useEffect(() => {
    if (open) setReviewerId("");
  }, [open]);

  // The two ids the backend refuses, so every pickable option is a legal one:
  // the reviewer who has it, and the submitter themselves.
  const excluded = new Set(
    [currentReviewerId, currentUserId].filter((id) => id != null),
  );
  const options = (approvers ?? []).filter((a) => !excluded.has(a.userId));

  const handleSubmit = () => {
    if (!reviewerId || submitting) return;
    onSubmit(Number(reviewerId));
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Change reviewer</DialogTitle>
        </DialogHeader>
        {options.length === 0 ? (
          <EmptyState
            what="There is nobody else to review this posting."
            how="Reassignment needs another colleague with posting-approval access, and you can't review your own posting."
            who="Ask an admin to grant someone that access."
          />
        ) : (
          <div className="space-y-4">
            <p className="text-sm text-slate-700">
              Only the new reviewer is told. The posting stays where it is.
            </p>
            <div className="space-y-1">
              <Label htmlFor="reassign-reviewer">Reviewer</Label>
              <p className="text-xs text-slate-500">
                The reviewer who has it now, and you, are both left out of this
                list.
              </p>
              <select
                id="reassign-reviewer"
                className="w-full rounded-md border border-slate-300 p-2 text-sm"
                value={reviewerId}
                onChange={(e) => setReviewerId(e.target.value)}
              >
                <option value="">Select a reviewer…</option>
                {options.map((a) => (
                  <option key={a.userId} value={a.userId}>
                    {a.name} ({a.email})
                  </option>
                ))}
              </select>
            </div>
          </div>
        )}
        <DialogFooter>
          <Button
            variant="outline"
            onClick={() => onOpenChange(false)}
            disabled={submitting}
          >
            Cancel
          </Button>
          <Button onClick={handleSubmit} disabled={!reviewerId || submitting}>
            Reassign
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export default ReassignReviewerDialog;
