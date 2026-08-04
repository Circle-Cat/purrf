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

/**
 * Dialog to submit a posting for review: pick a reviewer (excluding self) and
 * an optional message. There's no minimum pool-size requirement — if there's
 * at least one eligible reviewer to pick, Submit is enabled once one is
 * chosen; if there's none, the select simply has nothing to pick.
 *
 * @param {{open: boolean, approvers: object[], currentUserId: number,
 *          title?: string, submitting?: boolean, onSubmit: Function,
 *          onOpenChange: Function}} props
 */
const SubmitReviewDialog = ({
  open,
  approvers,
  currentUserId,
  title = "Submit for review",
  submitting = false,
  onSubmit,
  onOpenChange,
}) => {
  const options = (approvers ?? []).filter((a) => a.userId !== currentUserId);
  const [reviewerId, setReviewerId] = useState("");
  const [message, setMessage] = useState("");

  useEffect(() => {
    if (open) {
      setReviewerId("");
      setMessage("");
    }
  }, [open]);

  const handleSubmit = () => {
    if (!reviewerId || submitting) return;
    onSubmit({
      reviewerId: Number(reviewerId),
      message: message.trim() || null,
    });
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
        </DialogHeader>
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
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={handleSubmit} disabled={!reviewerId || submitting}>
            {title}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export default SubmitReviewDialog;
