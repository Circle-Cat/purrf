import {
  CalendarDays,
  History,
  ListChecks,
  Plus,
  UserCheck,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";

/**
 * One figure in the card header.
 *
 * @param {{label: string, value: string, hint?: string, tone?: string}} props
 * @returns {JSX.Element}
 */
const Stat = ({ label, value, hint, tone = "text-slate-900" }) => (
  <div className="min-w-0">
    <p className="text-xs uppercase tracking-wide text-slate-500">{label}</p>
    <p className={`text-2xl font-semibold tabular-nums mt-1 ${tone}`}>
      {value}
    </p>
    {hint && <p className="text-xs text-slate-400 mt-0.5">{hint}</p>}
  </div>
);

/**
 * TimeOffCard
 *
 * The leave module's whole presence on the personal dashboard, for two kinds of
 * people who overlap: those the leave system covers, and those somebody has
 * filed leave against.
 *
 * Covered people get the three figures answering "what can I spend" and the
 * things they come here to do. An approver gets one more button, the way into
 * the requests waiting on them. A manager outside the leave population still
 * decides their reports' requests, so they get the card too — but only the
 * Approvals button and the holiday list: 0.00h under Available would read as
 * "my leave is zero", and filing would be refused.
 *
 * There is no "awaiting a decision" badge. Beside an Approvals button it would
 * read as "waiting on you", and the viewer's own pending hours are already the
 * Pending figure.
 *
 * @param {object} props
 * @param {boolean} props.isCovered
 * @param {boolean} props.isApprover
 * @param {number} [props.approvalsPendingCount] - requests waiting on the viewer
 * @param {number} [props.available]
 * @param {number} [props.pending] - hours held by the viewer's own undecided requests
 * @param {number} [props.used]
 * @param {() => void} [props.onRequest]
 * @param {() => void} props.onViewHolidays
 * @param {() => void} [props.onViewRequests]
 * @param {() => void} [props.onViewLedger]
 * @param {() => void} [props.onViewApprovals]
 * @returns {JSX.Element|null}
 */
const TimeOffCard = ({
  isCovered,
  isApprover,
  approvalsPendingCount = 0,
  available = 0,
  pending = 0,
  used = 0,
  onRequest,
  onViewHolidays,
  onViewRequests,
  onViewLedger,
  onViewApprovals,
}) => {
  if (!isCovered && !isApprover) return null;

  const approvals = isApprover && (
    <Button size="sm" variant="outline" onClick={onViewApprovals}>
      <UserCheck size={15} />
      {approvalsPendingCount > 0
        ? `Approvals (${approvalsPendingCount})`
        : "Approvals"}
    </Button>
  );
  const holidays = (
    <Button size="sm" variant="outline" onClick={onViewHolidays}>
      <CalendarDays size={15} />
      Company holidays
    </Button>
  );

  return (
    <Card className="p-5 space-y-5">
      <h2 className="text-sm font-semibold text-slate-900">Time off</h2>

      {isCovered ? (
        <>
          <div className="grid grid-cols-3 gap-6">
            <Stat
              label="Available"
              value={`${available.toFixed(2)}h`}
              hint={`${(available / 8).toFixed(1)} days`}
              tone={available < 0 ? "text-rose-600" : "text-slate-900"}
            />
            <Stat
              label="Pending"
              value={`${pending.toFixed(2)}h`}
              hint="Requested, not yet decided"
            />
            <Stat
              label="Used"
              value={`${used.toFixed(2)}h`}
              hint="Approved and taken"
            />
          </div>

          <div className="flex flex-wrap gap-2 pt-1">
            <Button size="sm" onClick={onRequest}>
              <Plus size={15} />
              Request time off
            </Button>
            {holidays}
            <Button size="sm" variant="outline" onClick={onViewRequests}>
              <ListChecks size={15} />
              My requests
            </Button>
            <Button size="sm" variant="outline" onClick={onViewLedger}>
              <History size={15} />
              Balance history
            </Button>
            {approvals}
          </div>
        </>
      ) : (
        <>
          <p className="text-sm text-slate-500">
            Leave isn&apos;t tracked for your account.
          </p>
          <div className="flex flex-wrap gap-2">
            {approvals}
            {holidays}
          </div>
        </>
      )}
    </Card>
  );
};

export default TimeOffCard;
