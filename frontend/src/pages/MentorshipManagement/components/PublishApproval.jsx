import { useState } from "react";
import { Button } from "@/components/ui/button";
import {
  decideMentorshipApproval,
  reassignMentorshipApproval,
  requestMatchingPublish,
  withdrawMentorshipApproval,
} from "@/api/mentorshipApi";
import ApprovalRequestDialog from "@/components/approval/ApprovalRequestDialog";
import ApprovalDecisionDialog from "@/components/approval/ApprovalDecisionDialog";
import { useMentorshipApprovers } from "@/pages/MentorshipManagement/hooks/useMentorshipApprovers";
import { approvalPersonLabel } from "@/pages/MentorshipManagement/utils/approvalLabels";
import { useApprovalAction } from "@/pages/MentorshipManagement/hooks/useApprovalAction";

const sameUser = (a, b) => a != null && b != null && String(a) === String(b);

/**
 * Publishing a succeeded run's result, through an approval.
 *
 * With nothing waiting, an admin with write access asks a named reviewer to
 * publish; the button is off while anyone is editing or the saved result has
 * problems, and the last rejection's reason is shown under it. While a request
 * waits, everyone sees who it was sent to and by whom; its raiser can hand it
 * to another reviewer or withdraw it, and the reviewer it names approves or
 * rejects it here. Approving publishes at once, so it is confirmed first.
 *
 * Every action reloads the run afterwards: an approval clears the round's
 * run, and the page then says there is none.
 *
 * @param {object} props
 * @param {number|string} props.roundId The round.
 * @param {object} props.overview The run overview, with `publishRequest` and
 *   `lastPublishRejection`.
 * @param {boolean} props.editing This viewer is editing the result.
 * @param {boolean} props.canWrite The viewer holds mentorship write access.
 * @param {boolean} props.canApprove The viewer holds mentorship.approve.
 * @param {number|string|null} props.userId The viewer.
 * @param {() => Promise<void>} props.onChanged Reload the run.
 * @returns {JSX.Element|null}
 */
const PublishApproval = ({
  roundId,
  overview,
  editing,
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
  const pending = overview.publishRequest;
  const rejection = overview.lastPublishRejection;

  const act = async (call, done, fallback) => {
    if (await run(call, done, fallback)) setDialog(null);
  };

  if (pending) {
    const isRaiser = sameUser(pending.raisedBy?.userId, userId);
    const isReviewer = canApprove && sameUser(pending.reviewer?.userId, userId);
    return (
      <section
        aria-label="Publish approval"
        className="space-y-2 rounded-md border border-border p-3 text-sm"
      >
        <p>
          Waiting for approval — sent to {approvalPersonLabel(pending.reviewer)}{" "}
          by {approvalPersonLabel(pending.raisedBy)}.
        </p>
        {pending.reason ? (
          <p className="text-muted-foreground">Reason: {pending.reason}</p>
        ) : null}
        <div className="flex flex-wrap gap-2">
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
          open={dialog === "approve" || dialog === "reject"}
          onOpenChange={(open) => {
            if (!open) setDialog(null);
          }}
          decision={dialog === "reject" ? "reject" : "approve"}
          title={
            dialog === "reject" ? "Reject publishing" : "Approve and publish"
          }
          description={
            dialog === "reject"
              ? "The result is unlocked so it can be changed and sent again. Your reason is shown to the person who asked."
              : `This creates ${overview.matchedCount ?? 0} pairs and sets everyone's status in this round. It cannot be undone.`
          }
          submitting={busy}
          onConfirm={(comment) =>
            act(
              () =>
                decideMentorshipApproval(pending.requestId, {
                  decision: dialog === "reject" ? "reject" : "approve",
                  comment: dialog === "reject" ? comment : undefined,
                }),
              dialog === "reject"
                ? "Publishing rejected."
                : "Published. The pairs are in place.",
              dialog === "reject"
                ? "Could not reject the request."
                : "Could not publish.",
            )
          }
        />
      </section>
    );
  }

  if (!canWrite) return null;

  const blocked =
    editing ||
    overview.editLock != null ||
    (overview.problems ?? []).length > 0;
  return (
    <section aria-label="Publish approval" className="space-y-2 text-sm">
      <Button onClick={() => setDialog("request")} disabled={blocked || busy}>
        Request publishing
      </Button>
      {rejection ? (
        <p className="text-red-700">
          Publishing was rejected by {approvalPersonLabel(rejection.decidedBy)}
          {rejection.comment ? `: ${rejection.comment}` : "."}
        </p>
      ) : null}
      <ApprovalRequestDialog
        open={dialog === "request"}
        onOpenChange={(open) => setDialog(open ? "request" : null)}
        title="Request publishing"
        description="The result is locked until the reviewer decides. Approving it creates the pairs."
        reviewers={reviewers.approvers}
        reviewersLoading={reviewers.isLoading}
        reviewersError={reviewers.error}
        askReason
        confirmLabel="Send request"
        submitting={busy}
        onConfirm={({ reviewerId, reason }) =>
          act(
            () => requestMatchingPublish(roundId, { reviewerId, reason }),
            "Sent for approval.",
            "Could not send the request.",
          )
        }
      />
    </section>
  );
};

export default PublishApproval;
