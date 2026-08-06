import { ArrowLeft } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import {
  STATUS_LABEL,
  TYPE_LABEL,
  today,
} from "@/pages/LeavePrototype/leaveCalc";

/** Colour treatment per request status. */
const STATUS_STYLE = {
  pending: "bg-amber-50 text-amber-700 border-amber-200",
  approved: "bg-emerald-50 text-emerald-700 border-emerald-200",
  rejected: "bg-rose-50 text-rose-700 border-rose-200",
  withdrawn: "bg-slate-100 text-slate-500 border-slate-200",
  cancel_pending: "bg-amber-50 text-amber-700 border-amber-200",
  cancelled: "bg-slate-100 text-slate-500 border-slate-200",
};

/**
 * RequestsPage
 *
 * Every request this person has made, with the two actions that are still
 * open to them: withdrawing something nobody has decided yet, and asking to
 * cancel something already approved.
 *
 * A page rather than a dialog because it is the thing people scroll back
 * through — "when did I take those days in September" is a question about
 * history, not about the next request.
 *
 * @param {object} props
 * @param {Array<object>} props.requests
 * @param {() => void} props.onBack
 * @param {(id: number) => void} props.onWithdraw
 * @param {(id: number) => void} props.onRequestCancel
 * @returns {JSX.Element}
 */
const RequestsPage = ({ requests, onBack, onWithdraw, onRequestCancel }) => (
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
      <h1 className="text-xl font-semibold text-slate-900">My requests</h1>
      <p className="text-sm text-slate-500 mt-0.5">
        {requests.length} {requests.length === 1 ? "request" : "requests"} on
        file.
      </p>
    </header>

    <Card className="p-5">
      {requests.length === 0 ? (
        <p className="py-6 text-center text-sm text-slate-400">
          Nothing submitted yet.
        </p>
      ) : (
        <ul className="divide-y divide-slate-100">
          {requests.map((r) => (
            <li
              key={r.id}
              className="py-3 flex items-start justify-between gap-4"
            >
              <div className="min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-sm font-medium text-slate-900">
                    {TYPE_LABEL[r.type]}
                  </span>
                  <Badge
                    variant="outline"
                    className={`text-xs ${STATUS_STYLE[r.status]}`}
                  >
                    {STATUS_LABEL[r.status]}
                  </Badge>
                  {r.isOverdraft && (
                    <Badge
                      variant="outline"
                      className="text-xs bg-rose-50 text-rose-700 border-rose-200"
                    >
                      Overdraft
                    </Badge>
                  )}
                  {r.isLateNotice && (
                    <Badge
                      variant="outline"
                      className="text-xs bg-amber-50 text-amber-800 border-amber-200"
                    >
                      Short notice
                    </Badge>
                  )}
                </div>
                <p className="text-xs text-slate-500 mt-1 tabular-nums">
                  {r.startDate}
                  {r.endDate !== r.startDate && ` → ${r.endDate}`} · {r.hours}h
                  {r.decidedBy === "system" && " · auto-approved"}
                </p>
                {r.reason && (
                  <p className="text-xs text-slate-400 mt-0.5">{r.reason}</p>
                )}
                {r.rejectComment && (
                  <p className="text-xs text-rose-600 mt-1">
                    {r.decidedBy}: {r.rejectComment}
                  </p>
                )}
              </div>
              <div className="shrink-0">
                {r.status === "pending" && (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => onWithdraw(r.id)}
                  >
                    Withdraw
                  </Button>
                )}
                {r.status === "approved" && r.startDate >= today() && (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => onRequestCancel(r.id)}
                  >
                    Cancel
                  </Button>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
    </Card>
  </div>
);

export default RequestsPage;
