import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  AUTO_APPROVAL_NOTE,
  AUTO_APPROVED_LABEL,
  LEAVE_STATUS_LABELS,
  LEAVE_TYPE_EFFECT,
  LEAVE_TYPE_LABELS,
} from "@/constants/LeaveRequest";
import RequestSpan from "@/pages/Leave/components/RequestSpan";

/** How each state reads on somebody's own list. */
const OWN_STATUS_LABELS = {
  ...LEAVE_STATUS_LABELS,
  pending: "Waiting for your manager",
};

/**
 * MyRequestRow
 *
 * One of the signed-in employee's own requests.
 *
 * The hours are the point of reading this list: they are computed on the
 * server, skipping company holidays and the weekend, so three days off is not
 * always twenty-four hours. Nothing here recomputes them.
 *
 * Only a pending request offers Withdraw. Approval is the end of the line --
 * putting the hours back afterwards is an admin adjustment with a note on it --
 * so an approved request has no button rather than a button that fails.
 *
 * @param {{
 *   row: object,
 *   isWithdrawable: boolean,
 *   isWithdrawing: boolean,
 *   onWithdraw?: (requestId: number) => void,
 * }} props
 */
const MyRequestRow = ({ row, isWithdrawable, isWithdrawing, onWithdraw }) => {
  const effect = LEAVE_TYPE_EFFECT[row.type];

  return (
    <li className="flex flex-col gap-2 py-3 sm:flex-row sm:items-start sm:justify-between">
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant={effect?.variant ?? "secondary"}>
            {effect?.sign && `${effect.sign} `}
            {LEAVE_TYPE_LABELS[row.type] ?? row.type}
          </Badge>
          <span className="text-sm text-muted-foreground">
            {row.isAutoApproved
              ? AUTO_APPROVED_LABEL
              : (OWN_STATUS_LABELS[row.status] ?? row.status)}
          </span>
        </div>
        <RequestSpan row={row} className="mt-1 text-sm" />
        {row.reason && (
          <p className="mt-1 text-sm text-muted-foreground">{row.reason}</p>
        )}
        {row.isAutoApproved && (
          <p className="mt-1 text-sm text-muted-foreground">
            {AUTO_APPROVAL_NOTE}
          </p>
        )}
        {row.decisionComment && (
          <p className="mt-1 text-sm">{`Your manager's reason: ${row.decisionComment}`}</p>
        )}
        {row.isLateNotice && (
          <p className="mt-1 text-sm text-amber-700">
            {`Submitted with less than ${row.requiredNoticeWorkdays} working days' notice`}
          </p>
        )}
      </div>

      {isWithdrawable && (
        <div className="shrink-0">
          <Button
            variant="outline"
            disabled={isWithdrawing}
            onClick={() => onWithdraw(row.requestId)}
          >
            Withdraw
          </Button>
        </div>
      )}
    </li>
  );
};

export default MyRequestRow;
