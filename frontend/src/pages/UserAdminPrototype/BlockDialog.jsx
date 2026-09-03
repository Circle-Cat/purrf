import { useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import BlockImpact from "@/pages/UserAdminPrototype/BlockImpact";
import { fullName, impactFor } from "@/pages/UserAdminPrototype/accountState";
import { USER_ADMIN_HOLDERS } from "@/pages/UserAdminPrototype/mockData";

/**
 * BlockDialog
 *
 * One dialog for both sides of the design, because the evidence an operator
 * needs and the evidence a requester needs are the same. `mode` changes the
 * wording and the button, never the pre-flight.
 *
 * A reason is mandatory in both modes. It is the only durable record of why
 * this happened: the users table keeps current state, not history, so a block
 * with no reason can never be explained afterwards.
 *
 * Requesting also picks a reviewer from the user.admin holders, the same way a
 * posting is submitted for review. Naming a person is what makes the request
 * somebody's to answer; a queue addressed to a permission is addressed to
 * nobody.
 *
 * @param {{user: object|null, mode: "apply"|"request", onCancel: Function,
 *   onConfirm: Function}} props
 * @returns {JSX.Element}
 */
const BlockDialog = ({ user, mode, onCancel, onConfirm }) => {
  const [reason, setReason] = useState("");
  const [reviewerId, setReviewerId] = useState("");
  if (!user) return null;

  const requesting = mode === "request";
  const ready = reason.trim().length > 0 && (!requesting || reviewerId !== "");

  const reset = () => {
    setReason("");
    setReviewerId("");
  };

  const submit = () => {
    const reviewer = USER_ADMIN_HOLDERS.find(
      (h) => h.userId === Number(reviewerId),
    );
    onConfirm(reason.trim(), reviewer ?? null);
    reset();
  };

  const close = () => {
    reset();
    onCancel();
  };

  return (
    <Dialog open onOpenChange={(open) => !open && close()}>
      <DialogContent className="max-w-xl">
        <DialogHeader>
          <DialogTitle>
            {requesting ? "Request a block — " : "Block "}
            {fullName(user)}
          </DialogTitle>
        </DialogHeader>

        <p className="text-sm text-slate-600">
          {requesting
            ? "This does not block anyone yet. It goes to whoever holds user.admin, and nothing changes for this person until they approve it."
            : "This takes effect immediately. You hold user.admin, so no second approval is required."}
        </p>

        <BlockImpact impact={impactFor(user.userId)} />

        {requesting && (
          <div className="space-y-1">
            <Label htmlFor="block-reviewer">Reviewer</Label>
            <select
              id="block-reviewer"
              className="w-full rounded-md border border-slate-300 p-2 text-sm"
              value={reviewerId}
              onChange={(e) => setReviewerId(e.target.value)}
            >
              <option value="">Select a reviewer…</option>
              {USER_ADMIN_HOLDERS.map((holder) => (
                <option key={holder.userId} value={holder.userId}>
                  {holder.name} ({holder.email})
                </option>
              ))}
            </select>
          </div>
        )}

        <div className="space-y-1.5">
          <label
            className="text-sm font-medium text-slate-900"
            htmlFor="block-reason"
          >
            Reason — required
          </label>
          <Textarea
            id="block-reason"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="What happened, and what evidence supports it."
            rows={3}
          />
          <p className="text-xs text-slate-500">
            Stored with the account and shown to anyone who later asks why.
          </p>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={close}>
            Cancel
          </Button>
          <Button variant="destructive" disabled={!ready} onClick={submit}>
            {requesting ? "Submit request" : "Block"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export default BlockDialog;
