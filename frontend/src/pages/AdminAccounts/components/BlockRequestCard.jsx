import { useState } from "react";
import { Button } from "@/components/ui/button";
import ApprovalDecisionDialog from "@/components/approval/ApprovalDecisionDialog";
import AwaitingDecisionCard from "@/components/approval/AwaitingDecisionCard";
import BlockPreflight from "@/pages/AdminAccounts/components/BlockPreflight";
import { humanizeSource } from "@/pages/AdminAccounts/utils/blockRequests";
import {
  formatDateTimeWithZone,
  resolveViewerTimezone,
} from "@/utils/dateTime";

/**
 * The block request waiting on this viewer's decision, shown on the account it
 * is about. Rendered only when a pending request names the viewer as its
 * reviewer -- a request is nobody else's to see, which the endpoint enforces.
 *
 * Both decisions are confirmed in the shared decision dialog: approving blocks
 * at once, and rejecting asks for the reason the raiser is emailed. The dialog
 * stays open until the decision is recorded, so nothing reads the account
 * while the block is still being applied.
 *
 * Approving shows the same pre-flight the raiser read before sending the
 * request, read again when the confirm opens so it counts what the block
 * reaches now rather than when it was asked for.
 *
 * @param {Object} props
 * @param {Object} props.request - BlockRequestDto for this account.
 * @param {(note: string|null) => Promise<boolean>} props.onApprove - Approve
 *   and block; resolves true once recorded.
 * @param {(note: string) => Promise<boolean>} props.onReject - Turn the
 *   request down, with the reason; resolves true once recorded.
 * @param {boolean} props.submitting - A decision is in flight.
 * @param {Object|null} [props.preflight] - BlockPreflightDto for this
 *   account, or null while it is loading or could not be read.
 * @param {boolean} [props.preflightError] - The pre-flight could not be read.
 * @param {() => void} [props.onLoadPreflight] - Read the pre-flight; called
 *   when the approve confirm opens.
 */
const BlockRequestCard = ({
  request,
  onApprove,
  onReject,
  submitting,
  preflight = null,
  preflightError = false,
  onLoadPreflight,
}) => {
  const tz = resolveViewerTimezone();
  const [decision, setDecision] = useState(null);
  const source = humanizeSource(request.raisedFrom);
  const target = request.targetName || "this person";

  return (
    <AwaitingDecisionCard
      title="Block request awaiting your decision"
      meta={[
        `Raised by ${request.raisedByName}${
          source ? ` from ${source}` : ""
        } on ${formatDateTimeWithZone(request.raisedAt, tz)}`,
      ]}
      reason={request.reason}
    >
      <Button
        type="button"
        variant="destructive"
        onClick={() => {
          setDecision("approve");
          onLoadPreflight?.();
        }}
        disabled={submitting}
      >
        Approve and block
      </Button>
      <Button
        type="button"
        variant="outline"
        onClick={() => setDecision("reject")}
        disabled={submitting}
      >
        Reject
      </Button>
      <ApprovalDecisionDialog
        open={decision !== null}
        onOpenChange={(open) => !open && !submitting && setDecision(null)}
        decision={decision ?? "approve"}
        title={
          decision === "reject"
            ? "Reject this block request"
            : `Block ${target}?`
        }
        description={
          decision === "reject"
            ? `${target} is not blocked. ${request.raisedByName || "The raiser"} is told your reason.`
            : `${target} is blocked from Purrf as soon as you approve.`
        }
        onConfirm={async (comment) => {
          const recorded =
            decision === "reject"
              ? await onReject(comment)
              : await onApprove(null);
          if (recorded) setDecision(null);
        }}
        submitting={submitting}
      >
        {decision === "approve" && (
          <BlockPreflight preflight={preflight} error={preflightError} />
        )}
      </ApprovalDecisionDialog>
    </AwaitingDecisionCard>
  );
};

export default BlockRequestCard;
