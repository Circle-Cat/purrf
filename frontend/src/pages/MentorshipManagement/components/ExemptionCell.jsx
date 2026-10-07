import { useState } from "react";
import { Button } from "@/components/ui/button";
import {
  decideMentorshipApproval,
  reassignMentorshipApproval,
  requestMatchingExemption,
  withdrawMentorshipApproval,
} from "@/api/mentorshipApi";
import ApprovalRequestDialog from "@/components/approval/ApprovalRequestDialog";
import ApprovalDecisionDialog from "@/components/approval/ApprovalDecisionDialog";
import { useMentorshipApprovers } from "@/pages/MentorshipManagement/hooks/useMentorshipApprovers";
import { useApprovalAction } from "@/pages/MentorshipManagement/hooks/useApprovalAction";
import { approvalPersonLabel } from "@/pages/MentorshipManagement/utils/approvalLabels";
import { userDisplayName } from "@/utils/userName";

const sameUser = (a, b) => a != null && b != null && String(a) === String(b);

/**
 * One row's exemption, in the Needs exemption list.
 *
 * With nothing waiting, an admin with write access asks a named reviewer to
 * exempt the person in this round. While a request waits, the row says who it
 * was sent to; its raiser can hand it to another reviewer or withdraw it, and
 * the reviewer it names approves (after confirming) or rejects it with a
 * reason, right here.
 *
 * @param {object} props
 * @param {object} props.row The search row, with `exemptionRequest`.
 * @param {number|string} props.roundId The round searched.
 * @param {boolean} props.canWrite The viewer holds mentorship write access.
 * @param {boolean} props.canApprove The viewer holds mentorship.approve.
 * @param {number|string|null} props.userId The viewer.
 * @param {() => Promise<void>|void} props.onChanged Reload the list.
 * @returns {JSX.Element|null}
 */
const ExemptionCell = ({
  row,
  roundId,
  canWrite,
  canApprove,
  userId,
  onChanged,
}) => {
  // Which dialog is open: request, reassign, approve, reject, or none.
  const [dialog, setDialog] = useState(null);
  const reviewers = useMentorshipApprovers(
    dialog === "request" || dialog === "reassign",
  );
  const { busy, act: run } = useApprovalAction(onChanged);
  const pending = row.exemptionRequest;
  const name = userDisplayName(row);

  const act = async (call, done, fallback) => {
    if (await run(call, done, fallback)) setDialog(null);
  };

  if (!pending) {
    if (!canWrite) return null;
    return (
      <>
        <Button
          size="sm"
          variant="outline"
          onClick={() => setDialog("request")}
          disabled={busy}
        >
          Request exemption
        </Button>
        <ApprovalRequestDialog
          open={dialog === "request"}
          onOpenChange={(open) => setDialog(open ? "request" : null)}
          title={`Request an exemption for ${name}`}
          description="Approving it lets them into this round's matching pool, and nothing before this round counts against them again."
          reviewers={reviewers.approvers}
          reviewersLoading={reviewers.isLoading}
          reviewersError={reviewers.error}
          askReason
          confirmLabel="Send request"
          submitting={busy}
          onConfirm={({ reviewerId, reason }) =>
            act(
              () =>
                requestMatchingExemption(roundId, row.userId, {
                  reviewerId,
                  reason,
                }),
              "Sent for approval.",
              "Could not send the request.",
            )
          }
        />
      </>
    );
  }

  const isRaiser = sameUser(pending.raisedBy?.userId, userId);
  const isReviewer = canApprove && sameUser(pending.reviewer?.userId, userId);
  const rejecting = dialog === "reject";
  return (
    <div className="space-y-1 text-xs">
      <p>
        Waiting for approval — sent to {approvalPersonLabel(pending.reviewer)}
      </p>
      <div className="flex flex-wrap gap-1">
        {isReviewer ? (
          <>
            <Button
              size="sm"
              onClick={() => setDialog("approve")}
              disabled={busy}
            >
              Approve
            </Button>
            <Button
              size="sm"
              variant="outline"
              onClick={() => setDialog("reject")}
              disabled={busy}
            >
              Reject
            </Button>
          </>
        ) : null}
        {isRaiser ? (
          <>
            <Button
              size="sm"
              variant="outline"
              onClick={() => setDialog("reassign")}
              disabled={busy}
            >
              Reassign reviewer
            </Button>
            <Button
              size="sm"
              variant="outline"
              onClick={() =>
                act(
                  () => withdrawMentorshipApproval(pending.requestId),
                  "Request withdrawn.",
                  "Could not withdraw the request.",
                )
              }
              disabled={busy}
            >
              Withdraw
            </Button>
          </>
        ) : null}
      </div>
      <ApprovalRequestDialog
        open={dialog === "reassign"}
        onOpenChange={(open) => setDialog(open ? "reassign" : null)}
        title="Reassign reviewer"
        description="The request stays as it is; only who decides it changes. The new reviewer is told."
        confirmLabel="Reassign"
        reviewers={reviewers.approvers}
        reviewersLoading={reviewers.isLoading}
        reviewersError={reviewers.error}
        excludeUserIds={[pending.reviewer?.userId]}
        submitting={busy}
        onConfirm={({ reviewerId }) =>
          act(
            () => reassignMentorshipApproval(pending.requestId, reviewerId),
            "Request reassigned.",
            "Could not reassign the request.",
          )
        }
      />
      <ApprovalDecisionDialog
        open={dialog === "approve" || rejecting}
        onOpenChange={(open) => {
          if (!open) setDialog(null);
        }}
        decision={rejecting ? "reject" : "approve"}
        title={
          rejecting ? `Reject the exemption for ${name}` : `Exempt ${name}`
        }
        description={
          rejecting
            ? "Your reason is shown to the person who asked."
            : `${name} goes into this round's matching pool, and nothing before this round counts against them again. It cannot be undone.`
        }
        submitting={busy}
        onConfirm={(comment) =>
          act(
            () =>
              decideMentorshipApproval(pending.requestId, {
                decision: rejecting ? "reject" : "approve",
                comment: rejecting ? comment : undefined,
              }),
            rejecting ? "Exemption rejected." : "Exemption granted.",
            rejecting
              ? "Could not reject the request."
              : "Could not grant the exemption.",
          )
        }
      />
    </div>
  );
};

export default ExemptionCell;
