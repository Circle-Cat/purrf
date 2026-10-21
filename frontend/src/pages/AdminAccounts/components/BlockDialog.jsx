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
import ApprovalRequestDialog from "@/components/approval/ApprovalRequestDialog";
import { accountLabel } from "@/utils/userName";
import BlockPreflight from "@/pages/AdminAccounts/components/BlockPreflight";

const DEFAULT_REQUEST_DESCRIPTION =
  "This does not block anyone yet. It goes to the reviewer you name below, and nothing changes for this person until they approve it. You can change the reviewer or withdraw while it waits.";

/**
 * Block someone, or ask a named reviewer to.
 *
 * One component in two modes. The preflight block is word-for-word identical
 * in both -- the reviewer deciding a request must read exactly what the raiser
 * read. Request mode is the shared approval request dialog with the preflight
 * above its picker, and its reason is optional like every approval request's;
 * blocking directly requires one, because nobody else will ever be asked why.
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
 *          submitting?: boolean, requestDescription?: string}} props
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
 *   `reviewerId` is a number in request mode and null in direct mode, and
 *   `reason` is "" when a request gives none.
 * @param {boolean} [props.submitting] Disables both buttons while in flight.
 * @param {string} [props.requestDescription] Request-mode description, for a
 *   page that offers no way to change the reviewer or withdraw.
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
  requestDescription = DEFAULT_REQUEST_DESCRIPTION,
}) => {
  const isRequest = mode === "request";
  const [reason, setReason] = useState("");

  useEffect(() => {
    if (open) setReason("");
  }, [open]);

  const name = accountLabel(account);
  const preflightBlock = (
    <>
      <BlockPreflight preflight={preflight} timezone={timezone} />
      {preflightError && (
        <p className="text-sm text-slate-500">
          Couldn&apos;t read what this will affect. The block still does all of
          the above.
        </p>
      )}
    </>
  );

  if (isRequest) {
    const title = "Request a block";
    return (
      <ApprovalRequestDialog
        open={open}
        onOpenChange={onOpenChange}
        title={name ? `${title} — ${name}` : title}
        description={requestDescription}
        reviewers={holders}
        reviewersError={holdersError}
        excludeUserIds={[currentUserId, account?.userId]}
        reviewerHint="You and the person this is about are both left out of this list."
        emptyText="No one else holds user.admin, so there is nobody to send this to. Ask an admin to grant someone that access."
        askReason
        confirmLabel="Send request"
        onConfirm={({ reviewerId, reason: given }) =>
          onConfirm?.({ reason: given, reviewerId })
        }
        submitting={submitting}
      >
        {preflightBlock}
      </ApprovalRequestDialog>
    );
  }

  const canSubmit = Boolean(reason.trim()) && !submitting;
  const handleConfirm = () => {
    if (!canSubmit) return;
    onConfirm?.({ reason: reason.trim(), reviewerId: null });
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>
            {name ? `Block account — ${name}` : "Block account"}
          </DialogTitle>
          <DialogDescription className="text-slate-700">
            This takes effect immediately. You hold user.admin, so no second
            approval is required.
          </DialogDescription>
        </DialogHeader>
        {preflightBlock}
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
            variant="destructive"
            onClick={handleConfirm}
            disabled={!canSubmit}
          >
            Block
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export default BlockDialog;
