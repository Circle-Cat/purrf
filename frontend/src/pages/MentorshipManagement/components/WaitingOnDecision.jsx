import { useState } from "react";
import { Button } from "@/components/ui/button";
import {
  decideMentorshipApproval,
  reassignMentorshipApproval,
  withdrawMentorshipApproval,
} from "@/api/mentorshipApi";
import ApprovalRequestDialog from "@/components/approval/ApprovalRequestDialog";
import ApprovalDecisionDialog from "@/components/approval/ApprovalDecisionDialog";
import { useMentorshipApprovers } from "@/pages/MentorshipManagement/hooks/useMentorshipApprovers";
import { useApprovalAction } from "@/pages/MentorshipManagement/hooks/useApprovalAction";
import {
  approvalActionLabel,
  approvalPersonLabel,
} from "@/pages/MentorshipManagement/utils/approvalLabels";
import { userDisplayName } from "@/utils/userName";
import { statusRequestType } from "@/pages/MentorshipManagement/utils/statusRequestTypes";

const sameUser = (a, b) => a != null && b != null && String(a) === String(b);

/**
 * The requests about this person in this round that wait on a reviewer.
 *
 * Each row says what was asked, who asked and who decides. Its raiser can
 * withdraw it or hand it to another reviewer; the reviewer it names approves
 * (after reading what approving does) or rejects it with a reason. Nobody
 * else gets buttons, and nobody does while approvals are switched off.
 *
 * @param {object} props
 * @param {Object[]} props.requests The pending requests, from the detail API.
 * @param {Object[]} [props.pairs] The person's pairs this round, to name the
 *   pair a request is about.
 * @param {number} props.personId Who they are about, never their reviewer.
 * @param {string} props.personName Their name.
 * @param {number|string|null} props.viewerId The viewer.
 * @param {boolean} props.canApprove The viewer holds mentorship.approve.
 * @param {boolean} props.actionsOn Approvals are switched on for the viewer.
 * @param {() => Promise<void>|void} props.onChanged Reload the page.
 * @returns {JSX.Element|null}
 */
const WaitingOnDecision = ({
  requests,
  pairs = [],
  personId,
  personName,
  viewerId,
  canApprove,
  actionsOn,
  onChanged,
}) => {
  // {kind: "reassign"|"approve"|"reject", request} or null.
  const [dialog, setDialog] = useState(null);
  const reviewers = useMentorshipApprovers(dialog?.kind === "reassign");
  const { busy, act: run } = useApprovalAction(onChanged);
  if (!requests?.length) return null;

  const act = async (call, done, fallback) => {
    if (await run(call, done, fallback)) setDialog(null);
  };
  const open = dialog?.request;
  const rejecting = dialog?.kind === "reject";
  const typeOf = (request) => statusRequestType(request.action);

  const pairPartner = (request) => {
    const pair = pairs.find((p) => p.pairId === request.pairId);
    if (pair) return { id: pair.partner?.id, name: userDisplayName(pair.partner) };
    const other = sameUser(request.pair?.mentor?.userId, personId)
      ? request.pair?.mentee
      : request.pair?.mentor;
    return other ? { id: other.userId, name: approvalPersonLabel(other) } : null;
  };

  const aboutPair = (request) => {
    const partner = pairPartner(request);
    return partner?.name ? ` — about the pair with ${partner.name}` : "";
  };

  return (
    <section aria-label="Waiting on a decision" className="space-y-2">
      <h3 className="text-sm font-semibold">Waiting on a decision</h3>
      <ul className="divide-y divide-border text-sm">
        {requests.map((request) => {
          const isRaiser = sameUser(request.raisedBy?.userId, viewerId);
          const isReviewer =
            canApprove && sameUser(request.reviewer?.userId, viewerId);
          return (
            <li
              key={request.requestId}
              className="flex flex-wrap items-center gap-2 py-2"
            >
              <span className="flex-1">
                {approvalActionLabel(request.action)} — raised by{" "}
                {approvalPersonLabel(request.raisedBy)} · sent to{" "}
                {approvalPersonLabel(request.reviewer)}
                {aboutPair(request)}
              </span>
              {actionsOn && isReviewer ? (
                <>
                  <Button
                    size="sm"
                    onClick={() => setDialog({ kind: "approve", request })}
                    disabled={busy}
                  >
                    Approve
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => setDialog({ kind: "reject", request })}
                    disabled={busy}
                  >
                    Reject
                  </Button>
                </>
              ) : null}
              {actionsOn && isRaiser ? (
                <>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => setDialog({ kind: "reassign", request })}
                    disabled={busy}
                  >
                    Reassign
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() =>
                      act(
                        () => withdrawMentorshipApproval(request.requestId),
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
            </li>
          );
        })}
      </ul>
      <ApprovalRequestDialog
        open={dialog?.kind === "reassign"}
        onOpenChange={(isOpen) => {
          if (!isOpen) setDialog(null);
        }}
        title="Reassign reviewer"
        description="The request stays as it is; only who decides it changes. The new reviewer is told."
        confirmLabel="Reassign"
        reviewers={reviewers.approvers}
        reviewersLoading={reviewers.isLoading}
        reviewersError={reviewers.error}
        excludeUserIds={[
          open?.reviewer?.userId,
          personId,
          open && typeOf(open)?.partnerMayNotReview
            ? pairPartner(open)?.id
            : null,
        ]}
        submitting={busy}
        onConfirm={({ reviewerId }) =>
          act(
            () => reassignMentorshipApproval(open.requestId, reviewerId),
            "Request reassigned.",
            "Could not reassign the request.",
          )
        }
      />
      <ApprovalDecisionDialog
        open={dialog?.kind === "approve" || rejecting}
        onOpenChange={(isOpen) => {
          if (!isOpen) setDialog(null);
        }}
        decision={rejecting ? "reject" : "approve"}
        title={
          open
            ? `${rejecting ? "Reject" : "Approve"}: ${
                typeOf(open)?.label ?? approvalActionLabel(open.action)
              } — ${personName}`
            : ""
        }
        description={
          rejecting
            ? "Your reason is shown to the person who asked."
            : `${
                (open && typeOf(open)?.consequences(personName, {
                    partnerName: pairPartner(open)?.name,
                  })) ||
                "It takes effect at once and cannot be undone."
              }${open ? aboutPair(open) : ""}`
        }
        submitting={busy}
        onConfirm={(comment) =>
          act(
            () =>
              decideMentorshipApproval(open.requestId, {
                decision: rejecting ? "reject" : "approve",
                comment: rejecting ? comment : undefined,
              }),
            rejecting ? "Request rejected." : "Request approved.",
            rejecting
              ? "Could not reject the request."
              : "Could not approve the request.",
          )
        }
      />
    </section>
  );
};

export default WaitingOnDecision;
