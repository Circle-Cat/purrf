import { useState } from "react";
import { AlertTriangle, ArrowLeft, Clock, Inbox } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import TimeOffCard from "@/pages/LeavePrototype/TimeOffCard";
import { TYPE_LABEL } from "@/pages/LeavePrototype/leaveCalc";
import { ORG_LEDGER } from "@/pages/LeavePrototype/mockData";

/**
 * A pending request awaiting this manager's decision.
 *
 * The balance-after number is the point of the whole card: a manager should
 * not have to open a second page to find out that approving this puts someone
 * into overdraft.
 *
 * @param {object} props
 * @param {object} props.request
 * @param {(id: number) => void} props.onApprove
 * @param {(id: number, comment: string) => void} props.onReject
 * @returns {JSX.Element}
 */
const RequestCard = ({ request: r, onApprove, onReject }) => {
  const [rejecting, setRejecting] = useState(false);
  const [comment, setComment] = useState("");

  const spendsBalance = r.type === "paid";
  const delta = r.type === "exchange" ? r.hours : -r.hours;
  const balanceAfter =
    r.type === "sick" ? r.balanceBefore : r.balanceBefore + delta;
  const goesNegative = balanceAfter < 0;

  const isCancellation = r.status === "cancel_pending";

  return (
    <Card className="p-4">
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-sm font-semibold text-slate-900">
              {r.userName}
            </span>
            <span className="text-xs text-slate-400">{r.userLevel}</span>
            <Badge variant="outline" className="text-xs">
              {TYPE_LABEL[r.type]}
            </Badge>
            {isCancellation && (
              <Badge
                variant="outline"
                className="text-xs bg-slate-100 text-slate-600 border-slate-300"
              >
                Cancellation
              </Badge>
            )}
          </div>
          <p className="text-xs text-slate-500 mt-1 tabular-nums">
            {r.startDate}
            {r.endDate !== r.startDate && ` → ${r.endDate}`} · {r.hours}h
          </p>
          {r.reason && (
            <p className="text-sm text-slate-600 mt-2">{r.reason}</p>
          )}
        </div>

        {/* Balance impact */}
        <div className="shrink-0 text-right">
          <p className="text-xs uppercase tracking-wide text-slate-500">
            {isCancellation ? "Balance restored to" : "Balance after"}
          </p>
          <p
            className={`text-xl font-semibold tabular-nums ${
              goesNegative ? "text-rose-600" : "text-slate-900"
            }`}
          >
            {balanceAfter.toFixed(2)}h
          </p>
          <p className="text-xs text-slate-400 tabular-nums">
            from {r.balanceBefore.toFixed(2)}h
            {!spendsBalance && r.type === "sick" && " · unchanged"}
          </p>
        </div>
      </div>

      {/* Flags */}
      {(r.isOverdraft || r.isLateNotice) && (
        <div className="mt-3 space-y-1.5">
          {r.isOverdraft && (
            <div className="flex items-center gap-2 text-xs text-rose-700 bg-rose-50 border border-rose-200 rounded-md px-2.5 py-1.5">
              <AlertTriangle size={13} className="shrink-0" />
              Approving this puts {r.userName.split(" ")[0]} into overdraft.
            </div>
          )}
          {r.isLateNotice && (
            <div className="flex items-center gap-2 text-xs text-amber-800 bg-amber-50 border border-amber-200 rounded-md px-2.5 py-1.5">
              <Clock size={13} className="shrink-0" />
              Short notice: {r.requiredNoticeDays} working days expected,{" "}
              {r.actualNoticeDays} given.
            </div>
          )}
        </div>
      )}

      {/* Actions */}
      {rejecting ? (
        <div className="mt-3 space-y-2">
          <Textarea
            rows={2}
            autoFocus
            value={comment}
            placeholder="Tell them why — this is shown on their request."
            onChange={(e) => setComment(e.target.value)}
          />
          <div className="flex items-center gap-2">
            <Button
              size="sm"
              variant="destructive"
              disabled={!comment.trim()}
              onClick={() => onReject(r.id, comment.trim())}
            >
              {isCancellation ? "Decline cancellation" : "Reject"}
            </Button>
            <Button
              size="sm"
              variant="ghost"
              onClick={() => {
                setRejecting(false);
                setComment("");
              }}
            >
              Back
            </Button>
          </div>
        </div>
      ) : (
        <div className="mt-3 flex items-center gap-2">
          <Button size="sm" onClick={() => onApprove(r.id)}>
            {isCancellation ? "Allow cancellation" : "Approve"}
          </Button>
          <Button
            size="sm"
            variant="outline"
            onClick={() => setRejecting(true)}
          >
            {isCancellation ? "Decline" : "Reject"}
          </Button>
        </div>
      )}
    </Card>
  );
};

/** The manager in this prototype, and her own ledger for the covered case. */
const MANAGER_ID = 9;
const MANAGER_NAME = "Priya Raghavan";
const managerRows = ORG_LEDGER.filter((row) => row.userId === MANAGER_ID);
const MANAGER_BALANCE =
  Math.round(managerRows.reduce((sum, row) => sum + row.hours, 0) * 100) / 100;
const MANAGER_USED = managerRows
  .filter((row) => row.entryType === "leave_deduction")
  .reduce((sum, row) => sum - row.hours, 0);

/**
 * The approval queue itself: everything waiting on this manager.
 *
 * @param {object} props
 * @param {Array<object>} props.queue
 * @param {(id: number) => void} props.onApprove
 * @param {(id: number, comment: string) => void} props.onReject
 * @param {() => void} props.onBack
 * @returns {JSX.Element}
 */
const ApprovalsPage = ({ queue, onApprove, onReject, onBack }) => (
  <div className="p-6 space-y-4 max-w-4xl">
    <button
      type="button"
      onClick={onBack}
      className="flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-900 transition-colors"
    >
      <ArrowLeft size={15} />
      Back to dashboard
    </button>

    <header>
      <h1 className="text-xl font-semibold text-slate-900">Approvals</h1>
      <p className="text-sm text-slate-500 mt-0.5">
        Requests from your direct reports. You see these because Azure lists you
        as their manager — there is no separate role to grant.
      </p>
    </header>

    {queue.length === 0 ? (
      <Card className="p-10 text-center">
        <Inbox size={28} className="mx-auto text-slate-300" />
        <p className="text-sm text-slate-500 mt-3">Nothing waiting on you.</p>
        <p className="text-xs text-slate-400 mt-1">
          Submit something from the Employee page and it lands here.
        </p>
      </Card>
    ) : (
      <div className="space-y-3">
        {queue.map((r) => (
          <RequestCard
            key={r.id}
            request={r}
            onApprove={onApprove}
            onReject={onReject}
          />
        ))}
      </div>
    )}
  </div>
);

/**
 * ManagerView
 *
 * The manager's side, arranged the way it ships: the way in is a button on
 * the Time off card on their personal dashboard, and the queue is a page of
 * its own. Approving or rejecting there updates the same request objects the
 * Employee view reads, so a decision is visible on the employee's page
 * immediately.
 *
 * There is no separate manager role or permission — whoever Azure lists as
 * someone's manager is an approver once somebody has filed against them. And
 * an approver need not have leave of their own, so the dashboard can show the
 * card either way: a covered manager sees her figures with Approvals beside
 * them; one outside the leave population sees only Approvals and the holiday
 * list.
 *
 * Only Approvals is wired here. Filing, the holiday list and the histories are
 * the Employee view's, shown there for Dana.
 *
 * @param {object} props
 * @param {Array<object>} props.queue
 * @param {(id: number) => void} props.onApprove
 * @param {(id: number, comment: string) => void} props.onReject
 * @returns {JSX.Element}
 */
const ManagerView = ({ queue, onApprove, onReject }) => {
  const [page, setPage] = useState("dashboard");
  const [isCovered, setIsCovered] = useState(true);

  if (page === "approvals") {
    return (
      <ApprovalsPage
        queue={queue}
        onApprove={onApprove}
        onReject={onReject}
        onBack={() => setPage("dashboard")}
      />
    );
  }

  const coverageOptions = [
    { value: true, label: "Has leave of her own" },
    { value: false, label: "Outside the leave population" },
  ];

  return (
    <div className="p-6 space-y-4 max-w-4xl">
      <header>
        <h1 className="text-xl font-semibold text-slate-900">
          Personal dashboard
        </h1>
        <p className="text-sm text-slate-500 mt-0.5">
          {MANAGER_NAME} · manager of the Employee view&apos;s team
        </p>
      </header>

      <div
        role="radiogroup"
        aria-label="Manager coverage"
        className="inline-flex rounded-lg border border-slate-200 bg-white p-0.5 text-sm"
      >
        {coverageOptions.map((option) => (
          <button
            key={option.label}
            type="button"
            role="radio"
            aria-checked={isCovered === option.value}
            onClick={() => setIsCovered(option.value)}
            className={`rounded-md px-3 py-1.5 transition-colors ${
              isCovered === option.value
                ? "bg-slate-800 text-white"
                : "text-slate-600 hover:bg-slate-100"
            }`}
          >
            {option.label}
          </button>
        ))}
      </div>

      <TimeOffCard
        isCovered={isCovered}
        isApprover
        approvalsPendingCount={queue.length}
        available={MANAGER_BALANCE}
        pending={0}
        used={MANAGER_USED}
        onViewApprovals={() => setPage("approvals")}
      />
    </div>
  );
};

export default ManagerView;
