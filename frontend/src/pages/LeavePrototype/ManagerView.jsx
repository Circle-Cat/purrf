import { useState } from "react";
import { AlertTriangle, Clock, Inbox } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { TYPE_LABEL } from "@/pages/LeavePrototype/leaveCalc";

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

/**
 * ManagerView
 *
 * The queue of everything waiting on this manager. Approving or rejecting here
 * updates the same request objects the Employee view reads, so a decision made
 * on this page is visible on the employee's page immediately.
 *
 * There is no separate manager role or permission — whoever Azure lists as
 * someone's manager sees their requests here.
 *
 * @param {object} props
 * @param {Array<object>} props.queue
 * @param {(id: number) => void} props.onApprove
 * @param {(id: number, comment: string) => void} props.onReject
 * @returns {JSX.Element}
 */
const ManagerView = ({ queue, onApprove, onReject }) => (
  <div className="p-6 space-y-4 max-w-4xl">
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

export default ManagerView;
