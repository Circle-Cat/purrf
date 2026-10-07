import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  LEAVE_REQUEST_STATUS,
  LEAVE_STATUS_LABELS,
  LEAVE_TYPE_EFFECT,
  LEAVE_TYPE_LABELS,
} from "@/constants/LeaveRequest";
import {
  formatBusinessRange,
  formatTimeSpan,
} from "@/pages/Leave/utils/leaveDates";

/**
 * One request in an approver's list.
 *
 * The type is a badge carrying what it does to the balance: an exchange adds
 * hours, paid leave takes them away, and sick leave moves the balance not at
 * all. That is the question an approver is answering, so it is on the badge
 * rather than left to the reader to remember which type is which.
 *
 * A request still waiting also carries where the balance would land if it were
 * approved, next to where it stands now. That pair is the thing being decided,
 * so it is on the row rather than a page away -- and it is computed on the
 * server, so it cannot disagree with the ledger row an approval writes.
 *
 * Hours arrive as a string fixed to two decimals and are rendered as they
 * arrived. Nothing here adds, rounds or reformats them: the server is the only
 * place leave arithmetic happens, and a second implementation in the browser
 * would disagree with the ledger without saying so.
 *
 * Approving is irreversible -- there is no state for cancelling an approved
 * request -- so Approve asks once more in place. Rejecting asks for the reason
 * the employee is told, in place too. Both are inline rather than a dialog to
 * keep one control per row and avoid stacking a modal over a list the user is
 * reading.
 *
 * @param {{
 *   row: object,
 *   isDecidable: boolean,
 *   isDeciding: boolean,
 *   onDecide?: (requestId: number, approve: boolean, comment?: string) => void,
 * }} props
 */
const ApprovalRow = ({ row, isDecidable, isDeciding, onDecide }) => {
  // null, "approve" or "reject": which decision is being confirmed.
  const [confirming, setConfirming] = useState(null);
  const [reason, setReason] = useState("");
  const timeSpan = formatTimeSpan(row.startTime, row.endTime);
  const effect = LEAVE_TYPE_EFFECT[row.type];
  // Sent only while a request is still waiting: once decided, the ledger has
  // already moved and there is no "would" left to show.
  const hasBalanceHint =
    row.balanceBefore !== null && row.balanceBefore !== undefined;
  const landsBelowZero = Number(row.balanceAfter) < 0;

  return (
    <li className="flex flex-col gap-2 py-3 sm:flex-row sm:items-start sm:justify-between">
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-2">
          <p className="m-0 text-sm font-medium">
            {row.employeeName || "Unknown employee"}
            {row.employeeLdap && (
              <span className="font-normal text-muted-foreground">
                {` (${row.employeeLdap})`}
              </span>
            )}
          </p>
          <Badge variant={effect?.variant ?? "secondary"}>
            {effect?.sign && `${effect.sign} `}
            {LEAVE_TYPE_LABELS[row.type] ?? row.type}
          </Badge>
        </div>
        <p className="text-sm text-muted-foreground">
          {formatBusinessRange(row.startDate, row.endDate)}
          {timeSpan && ` · ${timeSpan}`}
          {` · ${row.hours} h`}
        </p>
        {row.reason && <p className="mt-1 text-sm">{row.reason}</p>}
        {/* For a waiting request the server works the overdraft out against
            the balance as it stands now, counting every paid hour still
            waiting -- so it can be set while "Balance after" is not, when this
            person has other requests waiting too. A decided request carries
            the mark it was approved on. */}
        {row.isOverdraft &&
          (isDecidable || row.status === LEAVE_REQUEST_STATUS.APPROVED) && (
            <p className="mt-1 text-sm text-rose-600">
              {isDecidable
                ? "Over the balance, counting their other waiting requests"
                : "Approved over the balance"}
            </p>
          )}
        {row.isLateNotice && (
          <p className="mt-1 text-sm text-amber-700">
            {/* Working days, not calendar days: the working week runs Tuesday
                to Saturday, so six working days is about eight days on a
                calendar. Saying "days" would read as the looser number. The
                count comes from the server -- deriving it here would put the
                notice rule in a second place. */}
            {`Submitted with less than ${row.requiredNoticeWorkdays} working days' notice`}
          </p>
        )}
        {!isDecidable && (
          <p className="mt-1 text-sm text-muted-foreground">
            {LEAVE_STATUS_LABELS[row.status] ?? row.status}
          </p>
        )}
        {!isDecidable && row.decisionComment && (
          <p className="mt-1 text-sm text-muted-foreground">
            {`Reason: ${row.decisionComment}`}
          </p>
        )}
      </div>

      {/* Right-hand column: what approving would do, and the controls that do
          it. Grouped so the figure sits above the buttons rather than being
          spread across the row by the outer justify-between. */}
      <div className="flex shrink-0 flex-col items-end gap-2">
        {hasBalanceHint && (
          <div className="text-right tabular-nums">
            <p className="m-0 text-xs uppercase tracking-wide text-muted-foreground">
              Balance after
            </p>
            <p
              className={`m-0 text-xl font-semibold ${
                landsBelowZero ? "text-rose-600" : ""
              }`}
            >
              {row.balanceAfter}h
            </p>
            <p className="m-0 text-xs text-muted-foreground">
              {`from ${row.balanceBefore}h`}
              {row.balanceAfter === row.balanceBefore && " · unchanged"}
            </p>
          </div>
        )}

        {isDecidable && confirming === null && (
          <div className="flex items-center gap-2">
            <Button
              disabled={isDeciding}
              onClick={() => setConfirming("approve")}
            >
              Approve
            </Button>
            <Button
              variant="outline"
              disabled={isDeciding}
              onClick={() => {
                setReason("");
                setConfirming("reject");
              }}
            >
              Reject
            </Button>
          </div>
        )}
        {isDecidable && confirming === "approve" && (
          <div className="flex items-center gap-2">
            <span className="text-sm text-muted-foreground">
              Approve for good?
            </span>
            <Button
              disabled={isDeciding}
              onClick={() => onDecide(row.requestId, true)}
            >
              Yes, approve
            </Button>
            <Button
              variant="outline"
              disabled={isDeciding}
              onClick={() => setConfirming(null)}
            >
              Cancel
            </Button>
          </div>
        )}
        {isDecidable && confirming === "reject" && (
          <div className="flex w-64 flex-col gap-2">
            <Label htmlFor={`reject-reason-${row.requestId}`}>
              Reason (required, the employee is told)
            </Label>
            <Textarea
              id={`reject-reason-${row.requestId}`}
              rows={2}
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              disabled={isDeciding}
            />
            <div className="flex justify-end gap-2">
              <Button
                variant="outline"
                disabled={isDeciding}
                onClick={() => setConfirming(null)}
              >
                Cancel
              </Button>
              <Button
                variant="destructive"
                disabled={isDeciding || reason.trim() === ""}
                onClick={() => onDecide(row.requestId, false, reason.trim())}
              >
                Reject
              </Button>
            </div>
          </div>
        )}
      </div>
    </li>
  );
};

export default ApprovalRow;
