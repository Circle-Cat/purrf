import { useState } from "react";
import { Label } from "@/components/ui/label";
import ApprovalRequestDialog from "@/components/approval/ApprovalRequestDialog";
import { useMentorshipApprovers } from "@/pages/MentorshipManagement/hooks/useMentorshipApprovers";
import { useApprovalAction } from "@/pages/MentorshipManagement/hooks/useApprovalAction";
import { approvalActionLabel } from "@/pages/MentorshipManagement/utils/approvalLabels";

/**
 * Ask a named reviewer to change a person's status in a round, or flag them.
 *
 * Nothing changes when it is sent: the reviewer decides. The kinds offered
 * come from the request types table; with only one, its name is shown
 * instead of a choice. Requests already waiting on this person are listed at
 * the top; another kind can still be asked for.
 *
 * @param {object} props
 * @param {boolean} props.open Whether the dialog is showing.
 * @param {(open: boolean) => void} props.onOpenChange Close handler.
 * @param {{userId: number, name: string}} props.person Who it is about.
 * @param {number|string} props.roundId The round.
 * @param {Object[]} props.types The request types available now.
 * @param {{requestId: number, action: string}[]} [props.pendingRequests]
 *   What already waits on a decision about them.
 * @param {() => Promise<void>|void} props.onSent Reload the page.
 * @returns {JSX.Element|null}
 */
const ChangeStatusDialog = ({
  open,
  onOpenChange,
  person,
  roundId,
  types,
  pendingRequests = [],
  onSent,
}) => {
  const [typeKey, setTypeKey] = useState(types[0]?.key ?? "");
  const reviewers = useMentorshipApprovers(open);
  const { busy, act } = useApprovalAction(onSent);
  const type = types.find((t) => t.key === typeKey) ?? types[0];
  if (!type) return null;

  return (
    <ApprovalRequestDialog
      open={open}
      onOpenChange={onOpenChange}
      title={`Change status / flag — ${person.name}`}
      description="Nothing changes yet. The reviewer you pick decides, and it only takes effect once they approve."
      reviewers={reviewers.approvers}
      reviewersLoading={reviewers.isLoading}
      reviewersError={reviewers.error}
      excludeUserIds={[person.userId]}
      reviewerHint={`${person.name} cannot review a request about themselves.`}
      askReason
      confirmLabel="Send for approval"
      submitting={busy}
      onConfirm={async ({ reviewerId, reason }) => {
        const sent = await act(
          () => type.raise(roundId, person.userId, { reviewerId, reason }),
          "Sent for approval.",
          "Could not send the request.",
        );
        if (sent) onOpenChange(false);
      }}
    >
      {pendingRequests.length > 0 ? (
        <p className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900">
          Already waiting on a decision:{" "}
          {pendingRequests.map((r) => approvalActionLabel(r.action)).join(", ")}
          . You can still ask for something else; each request is checked again
          when it is decided.
        </p>
      ) : null}
      <div className="space-y-1">
        {types.length > 1 ? (
          <>
            <Label htmlFor="status-request-type">What are you asking for</Label>
            <select
              id="status-request-type"
              className="w-full rounded-md border border-border p-2 text-sm"
              value={type.key}
              onChange={(e) => setTypeKey(e.target.value)}
              disabled={busy}
            >
              {types.map((t) => (
                <option key={t.key} value={t.key}>
                  {t.label}
                </option>
              ))}
            </select>
          </>
        ) : (
          <p className="text-sm font-medium">{type.label}</p>
        )}
      </div>
      <p className="text-sm text-muted-foreground">
        {type.consequences(person.name)}
      </p>
    </ApprovalRequestDialog>
  );
};

export default ChangeStatusDialog;
