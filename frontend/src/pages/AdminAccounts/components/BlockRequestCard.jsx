import { useState } from "react";
import { Button } from "@/components/ui/button";
import ApprovalDecisionDialog from "@/components/approval/ApprovalDecisionDialog";
import AwaitingDecisionCard from "@/components/approval/AwaitingDecisionCard";
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
 * @param {Object} props
 * @param {Object} props.request - BlockRequestDto for this account.
 * @param {(note: string|null) => Promise<boolean>} props.onApprove - Approve
 *   and block; resolves true once recorded.
 * @param {(note: string) => Promise<boolean>} props.onReject - Turn the
 *   request down, with the reason; resolves true once recorded.
 * @param {boolean} props.submitting - A decision is in flight.
 */
const BlockRequestCard = ({ request, onApprove, onReject, submitting }) => {
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
        onClick={() => setDecision("approve")}
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
            : `${target} is blocked from Purrf at once: their open applications close and their upcoming interviews are cancelled.`
        }
        onConfirm={async (comment) => {
          const recorded =
            decision === "reject"
              ? await onReject(comment)
              : await onApprove(null);
          if (recorded) setDecision(null);
        }}
        submitting={submitting}
      />
    </AwaitingDecisionCard>
  );
};

export default BlockRequestCard;
