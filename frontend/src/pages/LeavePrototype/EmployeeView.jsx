import { useState } from "react";
import { CalendarDays, History, Plus } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import RequestDialog from "@/pages/LeavePrototype/RequestDialog";
import {
  COMPANY_HOLIDAYS,
  CURRENT_USER,
} from "@/pages/LeavePrototype/mockData";
import {
  ENTRY_LABEL,
  STATUS_LABEL,
  TYPE_LABEL,
  groupHolidays,
  ledgerBalance,
  pendingReserved,
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
 * One number in the balance header.
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
 * EmployeeView
 *
 * What a regular employee sees: what they can spend, what they have booked,
 * how the balance got where it is, and when the office is closed anyway.
 *
 * Requesting happens in a dialog rather than a form pinned to the page. The
 * page is read most days and written a handful of times a year, so the form
 * earns its space only when someone asks for it.
 *
 * @param {object} props
 * @param {Array<object>} props.ledger - balance rows for the current user
 * @param {Array<object>} props.requests - the current user's requests
 * @param {(draft: object) => void} props.onSubmit
 * @param {(id: number) => void} props.onWithdraw
 * @param {(id: number) => void} props.onRequestCancel
 * @returns {JSX.Element}
 */
const EmployeeView = ({
  ledger,
  requests,
  onSubmit,
  onWithdraw,
  onRequestCancel,
}) => {
  const [requesting, setRequesting] = useState(false);

  const balance = ledgerBalance(ledger);
  const reserved = pendingReserved(requests);
  const available = Math.round((balance - reserved) * 100) / 100;

  const used = ledger
    .filter((r) => r.entryType === "leave_deduction")
    .reduce((s, r) => s + Math.abs(r.hours), 0);

  /** Newest first — the balance card deliberately does not explain itself. */
  const history = [...ledger].sort((a, b) =>
    a.effectiveDate === b.effectiveDate
      ? b.id - a.id
      : b.effectiveDate.localeCompare(a.effectiveDate),
  );

  /** Segments still ahead — a segment counts as upcoming until its last day. */
  const upcomingSegments = groupHolidays(COMPANY_HOLIDAYS).filter(
    (s) => s.end >= today(),
  );

  /**
   * The picker lists individual dates rather than whole segments: a break can
   * be only partly exchangeable, so the choice is per day even though a single
   * request may span several of them.
   */
  const exchangeableDays = upcomingSegments.flatMap((segment) =>
    segment.dates
      .filter(
        (date) =>
          date >= today() &&
          COMPANY_HOLIDAYS.find((h) => h.date === date)?.exchangeable,
      )
      .map((date) => ({ date, segment })),
  );

  return (
    <div className="p-6 space-y-6 max-w-5xl">
      <header className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold text-slate-900">Time off</h1>
          <p className="text-sm text-slate-500 mt-0.5">
            {CURRENT_USER.name} · {CURRENT_USER.level} · approver{" "}
            {CURRENT_USER.managerName}
          </p>
        </div>
        <Button onClick={() => setRequesting(true)} className="shrink-0">
          <Plus size={15} />
          Request time off
        </Button>
      </header>

      <RequestDialog
        open={requesting}
        onOpenChange={setRequesting}
        requests={requests}
        available={available}
        exchangeableDays={exchangeableDays}
        onSubmit={onSubmit}
      />

      {/* Balance */}
      <Card className="p-5">
        <div className="grid grid-cols-3 gap-6">
          <Stat
            label="Available"
            value={`${available.toFixed(2)}h`}
            hint={`${(available / 8).toFixed(1)} days`}
            tone={available < 0 ? "text-rose-600" : "text-slate-900"}
          />
          <Stat
            label="Reserved"
            value={`${reserved.toFixed(2)}h`}
            hint="Held by requests awaiting a decision"
          />
          <Stat
            label="Used"
            value={`${used.toFixed(2)}h`}
            hint="Approved and taken"
          />
        </div>
      </Card>

      {/* My requests */}
      <Card className="p-5">
        <h2 className="text-sm font-semibold text-slate-900 mb-3">
          My requests
        </h2>
        {requests.length === 0 ? (
          <div className="py-6 text-center">
            <p className="text-sm text-slate-400">Nothing submitted yet.</p>
            <Button
              variant="outline"
              size="sm"
              className="mt-3"
              onClick={() => setRequesting(true)}
            >
              Request time off
            </Button>
          </div>
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
                    {r.endDate !== r.startDate && ` → ${r.endDate}`} · {r.hours}
                    h{r.decidedBy === "system" && " · auto-approved"}
                  </p>
                  {r.reason && (
                    <p className="text-xs text-slate-400 mt-0.5 truncate">
                      {r.reason}
                    </p>
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

      {/* Balance history */}
      <Card className="p-5">
        <div className="flex items-center gap-2 mb-1">
          <History size={15} className="text-slate-400" />
          <h2 className="text-sm font-semibold text-slate-900">
            Balance history
          </h2>
        </div>
        <p className="text-xs text-slate-500 mb-3">
          Every change to your balance, newest first. Entries are only ever
          added — a correction is a new line, never an edit to an old one.
        </p>
        <ul className="divide-y divide-slate-100">
          {history.map((row) => (
            <li
              key={row.id}
              className="py-2.5 flex items-baseline justify-between gap-4"
            >
              <div className="min-w-0">
                <span className="text-sm text-slate-800">
                  {ENTRY_LABEL[row.entryType] ?? row.entryType}
                </span>
                {row.note && (
                  <p className="text-xs text-slate-400 mt-0.5">{row.note}</p>
                )}
              </div>
              <div className="shrink-0 text-right">
                <span
                  className={`text-sm font-medium tabular-nums ${
                    row.hours < 0 ? "text-rose-600" : "text-emerald-700"
                  }`}
                >
                  {row.hours > 0 ? "+" : ""}
                  {row.hours.toFixed(2)}h
                </span>
                <p className="text-xs text-slate-400 tabular-nums">
                  {row.effectiveDate}
                </p>
              </div>
            </li>
          ))}
        </ul>
        {/* Foots the list, and reconciles it with the Available figure up top
            — otherwise the page shows two totals and no way to tell which one
            is the real balance. */}
        <div className="mt-3 pt-3 border-t border-slate-200 space-y-1">
          <div className="flex items-baseline justify-between">
            <span className="text-sm font-medium text-slate-900">
              Total on record
            </span>
            <span className="text-sm font-semibold tabular-nums text-slate-900">
              {balance.toFixed(2)}h
            </span>
          </div>
          {reserved > 0 && (
            <>
              <div className="flex items-baseline justify-between text-slate-500">
                <span className="text-sm">Less reserved by pending</span>
                <span className="text-sm tabular-nums">
                  −{reserved.toFixed(2)}h
                </span>
              </div>
              <div className="flex items-baseline justify-between pt-1">
                <span className="text-sm font-medium text-slate-900">
                  Available to request
                </span>
                <span className="text-sm font-semibold tabular-nums text-slate-900">
                  {available.toFixed(2)}h
                </span>
              </div>
            </>
          )}
        </div>
      </Card>

      {/* Company holidays */}
      <Card className="p-5">
        <div className="flex items-center gap-2 mb-3">
          <CalendarDays size={15} className="text-slate-400" />
          <h2 className="text-sm font-semibold text-slate-900">
            Company holidays
          </h2>
        </div>
        <p className="text-xs text-slate-500 mb-3">
          You do not request these — the office is closed. Days marked
          exchangeable can be worked in trade for 8h of paid leave.
        </p>
        <ul className="divide-y divide-slate-100">
          {upcomingSegments.map((s) => (
            <li
              key={`${s.name}-${s.start}`}
              className="py-2.5 flex items-center justify-between gap-4 text-sm"
            >
              <div className="min-w-0">
                <span className="tabular-nums text-slate-500 mr-3">
                  {s.days === 1 ? s.start : `${s.start} – ${s.end}`}
                </span>
                <span className="text-slate-700">{s.name}</span>
                {s.days > 1 && (
                  <span className="text-xs text-slate-400 ml-2">
                    {s.days} days
                  </span>
                )}
              </div>
              {s.exchangeableDays > 0 && (
                <Badge variant="outline" className="text-xs shrink-0">
                  {s.exchangeableDays === s.days
                    ? "Exchangeable"
                    : `${s.exchangeableDays} of ${s.days} exchangeable`}
                </Badge>
              )}
            </li>
          ))}
        </ul>
      </Card>
    </div>
  );
};

export default EmployeeView;
