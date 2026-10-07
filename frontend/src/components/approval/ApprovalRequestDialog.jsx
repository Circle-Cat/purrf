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
 * Send an approval request to a named reviewer, or hand one to a different
 * reviewer. Shared by every kind of approval: the caller loads the reviewers
 * it may name and says what the request is.
 *
 * Every option is one the backend accepts: `excludeUserIds` drops the people
 * who may not review it (the caller, the reviewer it already has, the person
 * it is about). The reason is always optional. Anything a particular request
 * needs shown above the picker goes in `children`.
 *
 * @param {object} props
 * @param {boolean} props.open Whether the dialog is showing.
 * @param {(open: boolean) => void} props.onOpenChange Close handler.
 * @param {string} props.title Dialog title.
 * @param {string} props.description What sending it does.
 * @param {{userId: number|string, name?: string|null}[]} props.reviewers
 *   The people the request may be sent to.
 * @param {boolean} [props.reviewersLoading] The reviewers are still loading.
 * @param {boolean} [props.reviewersError] The reviewers could not be loaded.
 * @param {(number|string|null|undefined)[]} [props.excludeUserIds] People to
 *   leave out of the picker.
 * @param {boolean} [props.askReason] Offer an optional reason.
 * @param {string} [props.reasonLabel] The reason box's label.
 * @param {string} [props.reviewerHint] Said under the picker's label, such
 *   as who is left out of it and why.
 * @param {(reviewer: {userId: number|string, name?: string|null}) => string}
 *   [props.optionLabel] How each reviewer reads in the picker.
 * @param {string} props.confirmLabel The send button's label.
 * @param {string} [props.emptyText] Said when nobody can be picked.
 * @param {import("react").ReactNode} [props.emptyContent] Shown in place of
 *   the picker when nobody can be picked, for a caller that has more to say
 *   than one line.
 * @param {import("react").ReactNode} [props.children] Shown above the picker.
 * @param {({reviewerId: number, reason: string}) => void} props.onConfirm
 *   Called with the chosen reviewer and the trimmed reason ("" when none).
 * @param {boolean} [props.submitting] Disables the controls while in flight.
 * @returns {JSX.Element}
 */
const ApprovalRequestDialog = ({
  open,
  onOpenChange,
  title,
  description,
  reviewers,
  reviewersLoading = false,
  reviewersError = false,
  excludeUserIds = [],
  askReason = false,
  reasonLabel = "Reason (optional)",
  reviewerHint = null,
  optionLabel = (r) => r.name || `ID ${r.userId}`,
  confirmLabel,
  emptyText = "Nobody else can review this.",
  emptyContent = null,
  children = null,
  onConfirm,
  submitting = false,
}) => {
  const [reviewerId, setReviewerId] = useState("");
  const [reason, setReason] = useState("");

  useEffect(() => {
    if (open) {
      setReviewerId("");
      setReason("");
    }
  }, [open]);

  const excluded = new Set(
    excludeUserIds.filter((id) => id != null).map((id) => String(id)),
  );
  const options = (reviewers ?? []).filter(
    (r) => !excluded.has(String(r.userId)),
  );
  const ready = reviewerId !== "";
  const empty = !reviewersLoading && options.length === 0;

  const submit = () => {
    if (!ready || submitting) return;
    onConfirm({ reviewerId: Number(reviewerId), reason: reason.trim() });
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>{description}</DialogDescription>
        </DialogHeader>
        {children}
        {reviewersError ? (
          <p className="text-sm text-muted-foreground">
            Couldn&apos;t load the reviewers. Close this and try again.
          </p>
        ) : empty && emptyContent ? (
          emptyContent
        ) : (
          <div className="space-y-1">
            <Label htmlFor="approval-reviewer">Reviewer</Label>
            {reviewerHint ? (
              <p className="text-xs text-muted-foreground">{reviewerHint}</p>
            ) : null}
            <select
              id="approval-reviewer"
              className="w-full rounded-md border border-border p-2 text-sm"
              value={reviewerId}
              onChange={(e) => setReviewerId(e.target.value)}
              disabled={reviewersLoading || submitting}
            >
              <option value="">
                {reviewersLoading ? "Loading reviewers…" : "Select a reviewer…"}
              </option>
              {options.map((r) => (
                <option key={r.userId} value={r.userId}>
                  {optionLabel(r)}
                </option>
              ))}
            </select>
            {empty ? (
              <p className="text-xs text-muted-foreground">{emptyText}</p>
            ) : null}
          </div>
        )}
        {askReason ? (
          <div className="space-y-1">
            <Label htmlFor="approval-reason">{reasonLabel}</Label>
            <Textarea
              id="approval-reason"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
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
          <Button onClick={submit} disabled={!ready || submitting}>
            {confirmLabel}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export default ApprovalRequestDialog;
