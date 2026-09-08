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
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { accountLabel } from "@/utils/userName";
import { pickableReviewers } from "@/utils/blockReviewers";
import BlockPreflight from "@/pages/AdminAccounts/components/BlockPreflight";

/**
 * Block someone, or ask a named reviewer to.
 *
 * One component in two modes. The preflight block is word-for-word identical
 * in both -- the reviewer deciding a request must read exactly what the raiser
 * read. Only three things differ: the opening sentence, the reviewer picker
 * (request mode only), and the button label.
 *
 * A failed or still-loading preflight never blocks the dialog: the counts are
 * context for a decision, not a precondition for taking it.
 *
 * @param {{open: boolean, onOpenChange: Function, mode: "direct"|"request",
 *          account?: {userId?: number, firstName?: string, lastName?: string,
 *                     name?: string, primaryEmail?: string}|null,
 *          preflight?: {applicationCount: number, interviewTimes: string[]}|null,
 *          preflightError?: boolean, holders?: {userId: number, name: string}[],
 *          holdersError?: boolean, currentUserId?: number, onConfirm: Function,
 *          submitting?: boolean}} props
 * @param {boolean} props.open Whether the dialog is showing.
 * @param {Function} props.onOpenChange Called with the next open state.
 * @param {"direct"|"request"} props.mode `direct` blocks immediately; `request`
 *   sends the decision to a named reviewer and changes nothing yet.
 * @param {object|null} [props.account] The account being blocked; named in the
 *   title when it resolves to something. Either a first/last pair (the account
 *   console) or a single resolved `name` (the recruiting pages, which never
 *   hold a candidate's name split in two).
 * @param {object|null} [props.preflight] Counts and dates from the preflight
 *   endpoint, or null while it is loading or could not be read.
 * @param {boolean} [props.preflightError] The caller could not read the
 *   preflight. Stated, not fatal.
 * @param {{userId: number, name: string}[]} [props.holders] Pickable reviewers
 *   for request mode: active `user.admin` holders.
 * @param {string} [props.timezone] Passed through to the pre-flight so a
 *   caller with a profile zone does not get browser-zone dates in the middle
 *   of a page rendered in profile zone.
 * @param {boolean} [props.holdersError] The reviewer list could not be read.
 *   Distinct from an empty one: an empty list is a fact about the org, a failed
 *   read is a fact about the request.
 * @param {number} [props.currentUserId] Excluded from the reviewer options --
 *   nobody reviews their own request.
 * @param {Function} props.onConfirm Called with `{reason, reviewerId}`;
 *   `reviewerId` is a number in request mode and null in direct mode.
 * @param {boolean} [props.submitting] Disables both buttons while in flight.
 * @returns {JSX.Element}
 */
const BlockDialog = ({
  open,
  onOpenChange,
  mode,
  account,
  preflight = null,
  preflightError = false,
  holders,
  timezone,
  holdersError = false,
  currentUserId,
  onConfirm,
  submitting = false,
}) => {
  const isRequest = mode === "request";
  const options = pickableReviewers(holders, [currentUserId, account?.userId]);
  const [reason, setReason] = useState("");
  const [reviewerId, setReviewerId] = useState("");

  useEffect(() => {
    if (open) {
      setReason("");
      setReviewerId("");
    }
  }, [open]);

  const name = accountLabel(account);
  const title = isRequest ? "Request a block" : "Block account";
  const submitLabel = isRequest ? "Send request" : "Block";
  const canSubmit =
    Boolean(reason.trim()) &&
    (!isRequest || Boolean(reviewerId)) &&
    !submitting;

  const handleConfirm = () => {
    if (!canSubmit) return;
    onConfirm?.({
      reason: reason.trim(),
      reviewerId: isRequest ? Number(reviewerId) : null,
    });
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{name ? `${title} — ${name}` : title}</DialogTitle>
          <DialogDescription className="text-slate-700">
            {isRequest
              ? "This does not block anyone yet. It goes to the reviewer you name below, and nothing changes for this person until they approve it."
              : "This takes effect immediately. You hold user.admin, so no second approval is required."}
          </DialogDescription>
        </DialogHeader>
        <BlockPreflight preflight={preflight} timezone={timezone} />
        {preflightError && (
          <p className="text-sm text-slate-500">
            Couldn&apos;t read what this will affect. The block still does all
            of the above.
          </p>
        )}
        {isRequest &&
          (holdersError ? (
            <p className="text-sm text-slate-500">
              Couldn&apos;t load the reviewers to pick from. Close this and try
              again.
            </p>
          ) : options.length === 0 ? (
            <p className="text-sm text-slate-500">
              No one else holds user.admin, so there is nobody to send this to.
              Ask an admin to grant someone that access.
            </p>
          ) : (
            <div className="space-y-1">
              <Label htmlFor="reviewer">Reviewer</Label>
              <p className="text-xs text-slate-500">
                You and the person this is about are both left out of this list.
              </p>
              <select
                id="reviewer"
                className="w-full rounded-md border border-slate-300 p-2 text-sm"
                value={reviewerId}
                onChange={(e) => setReviewerId(e.target.value)}
              >
                <option value="">Select a reviewer…</option>
                {options.map((holder) => (
                  <option key={holder.userId} value={holder.userId}>
                    {holder.name}
                  </option>
                ))}
              </select>
            </div>
          ))}
        <div className="space-y-1">
          <Label htmlFor="block-reason">
            Reason — required, kept with the record
          </Label>
          <Textarea
            id="block-reason"
            rows={3}
            value={reason}
            onChange={(e) => setReason(e.target.value)}
          />
        </div>
        <DialogFooter>
          <Button
            variant="outline"
            onClick={() => onOpenChange?.(false)}
            disabled={submitting}
          >
            Cancel
          </Button>
          <Button
            variant={isRequest ? "default" : "destructive"}
            onClick={handleConfirm}
            disabled={!canSubmit}
          >
            {submitLabel}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export default BlockDialog;
