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
import { Textarea } from "@/components/ui/textarea";

/** Minimum active approvers required to submit (mirrors backend MIN_APPROVER_POOL). */
const MIN_APPROVERS = 2;

/**
 * Dialog to submit a posting for review: pick a reviewer (excluding self) and
 * an optional message. Submit is disabled when the TOTAL active-approver pool
 * (before self-exclusion) is below MIN_APPROVER_POOL=2, matching the backend floor.
 *
 * @param {{open: boolean, approvers: object[], currentUserId: number,
 *          onSubmit: Function, onOpenChange: Function}} props
 */
const SubmitReviewDialog = ({
  open,
  approvers,
  currentUserId,
  onSubmit,
  onOpenChange,
}) => {
  const options = (approvers ?? []).filter((a) => a.userId !== currentUserId);
  // Gate mirrors backend MIN_APPROVER_POOL check: total active-approver-pool size,
  // NOT the self-excluded selectable list (self-review is a separate backend check).
  const poolTooSmall = (approvers ?? []).length < MIN_APPROVERS;
  const [reviewerId, setReviewerId] = useState("");
  const [message, setMessage] = useState("");

  useEffect(() => {
    if (open) {
      setReviewerId("");
      setMessage("");
    }
  }, [open]);

  const handleSubmit = () => {
    if (!reviewerId) return;
    onSubmit({
      reviewerId: Number(reviewerId),
      message: message.trim() || null,
    });
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Submit for review</DialogTitle>
        </DialogHeader>
        {poolTooSmall ? (
          <p className="text-sm text-red-600">
            Need at least 2 approvers in the pool before submitting for review.
          </p>
        ) : (
          <div className="space-y-4">
            <div className="space-y-1">
              <Label htmlFor="reviewer">Reviewer</Label>
              <select
                id="reviewer"
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
            <div className="space-y-1">
              <Label htmlFor="message">Message</Label>
              <Textarea
                id="message"
                rows={3}
                value={message}
                onChange={(e) => setMessage(e.target.value)}
              />
            </div>
          </div>
        )}
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={handleSubmit} disabled={poolTooSmall || !reviewerId}>
            Submit
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export default SubmitReviewDialog;
