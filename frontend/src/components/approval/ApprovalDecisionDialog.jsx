import { useEffect, useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";

/**
 * Confirm a reviewer's decision before it is sent, for any kind of approval.
 * Rejecting asks for the reason, which the raiser is shown; approving asks
 * for nothing but a second click, because an approval acts at once and
 * cannot be taken back.
 *
 * @param {object} props
 * @param {boolean} props.open Whether the dialog is showing.
 * @param {(open: boolean) => void} props.onOpenChange Close handler.
 * @param {"approve"|"reject"} props.decision Which decision is confirmed.
 * @param {string} props.title Dialog title.
 * @param {string} props.description What the decision does.
 * @param {(comment: string) => void} props.onConfirm Called with the trimmed
 *   reason, "" for an approval.
 * @param {boolean} [props.submitting] Disables the controls while in flight.
 * @returns {JSX.Element}
 */
const ApprovalDecisionDialog = ({
  open,
  onOpenChange,
  decision,
  title,
  description,
  onConfirm,
  submitting = false,
}) => {
  const [comment, setComment] = useState("");
  const rejecting = decision === "reject";

  useEffect(() => {
    if (open) setComment("");
  }, [open]);

  const ready = !rejecting || comment.trim() !== "";
  const submit = () => {
    if (!ready || submitting) return;
    onConfirm(comment.trim());
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>{description}</DialogDescription>
        </DialogHeader>
        {rejecting ? (
          <div className="space-y-1">
            <Label htmlFor="approval-decision-reason">Reason</Label>
            <Textarea
              id="approval-decision-reason"
              value={comment}
              onChange={(e) => setComment(e.target.value)}
              disabled={submitting}
            />
          </div>
        ) : null}
        <DialogFooter>
          <Button
            variant="outline"
            onClick={() => onOpenChange(false)}
            disabled={submitting}
          >
            Cancel
          </Button>
          <Button
            variant={rejecting ? "destructive" : "default"}
            onClick={submit}
            disabled={!ready || submitting}
          >
            {rejecting ? "Reject" : "Approve"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export default ApprovalDecisionDialog;
