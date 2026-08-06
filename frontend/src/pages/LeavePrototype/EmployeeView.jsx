import { useMemo, useState } from "react";
import {
  AlertTriangle,
  CalendarDays,
  Check,
  History,
  Info,
  X,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  COMPANY_HOLIDAYS,
  CURRENT_USER,
  SICK_AUTO_APPROVE_HOURS,
} from "@/pages/LeavePrototype/mockData";
import {
  ENTRY_LABEL,
  STATUS_LABEL,
  TYPE_LABEL,
  breakdownRange,
  isAutoApproved,
  ledgerBalance,
  pendingReserved,
  today,
  validateDraft,
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
 * What a regular employee sees: their balance, the company holiday calendar,
 * the request form, and their own request history. The form computes hours
 * live and shows which days it skipped, because "I asked for five days and it
 * says sixteen hours" is the first question anyone asks.
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
  const [type, setType] = useState("paid");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [reason, setReason] = useState("");

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

  /** Exchange is always a single worked day, so the end date follows the start. */
  const effectiveEnd = type === "exchange" ? startDate : endDate;

  const breakdown = useMemo(
    () =>
      startDate && effectiveEnd && effectiveEnd >= startDate
        ? breakdownRange(startDate, effectiveEnd)
        : null,
    [startDate, effectiveEnd],
  );

  const draft = {
    type,
    startDate,
    endDate: effectiveEnd,
    hours: type === "exchange" ? 8 : (breakdown?.hours ?? 0),
  };

  const { error, warnings } = startDate
    ? validateDraft(draft, requests, available)
    : { error: null, warnings: [] };

  const canSubmit = Boolean(startDate && effectiveEnd) && !error;

  const submit = () => {
    if (!canSubmit) return;
    onSubmit({ ...draft, reason });
    setStartDate("");
    setEndDate("");
    setReason("");
  };

  const upcomingHolidays = COMPANY_HOLIDAYS.filter((h) => h.date >= today());

  return (
    <div className="p-6 space-y-6 max-w-5xl">
      <header>
        <h1 className="text-xl font-semibold text-slate-900">Time off</h1>
        <p className="text-sm text-slate-500 mt-0.5">
          {CURRENT_USER.name} · {CURRENT_USER.level} · approver{" "}
          {CURRENT_USER.managerName}
        </p>
      </header>

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
            hint="Held by pending requests"
          />
          <Stat
            label="Used"
            value={`${used.toFixed(2)}h`}
            hint="Approved and taken"
          />
        </div>
      </Card>

      {/* Request form */}
      <Card className="p-5 space-y-4">
        <h2 className="text-sm font-semibold text-slate-900">
          Request time off
        </h2>

        <div className="grid sm:grid-cols-3 gap-4">
          <div className="space-y-1.5">
            <Label htmlFor="leave-type">Type</Label>
            <Select value={type} onValueChange={setType}>
              <SelectTrigger id="leave-type">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="paid">Paid leave</SelectItem>
                <SelectItem value="sick">Sick leave</SelectItem>
                <SelectItem value="exchange">
                  Work a holiday (exchange)
                </SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="leave-start">
              {type === "exchange" ? "Holiday to work" : "First day"}
            </Label>
            {type === "exchange" ? (
              <Select value={startDate} onValueChange={setStartDate}>
                <SelectTrigger id="leave-start">
                  <SelectValue placeholder="Pick a holiday" />
                </SelectTrigger>
                <SelectContent>
                  {COMPANY_HOLIDAYS.filter(
                    (h) => h.exchangeable && h.date >= today(),
                  ).map((h) => (
                    <SelectItem key={h.date} value={h.date}>
                      {h.date} · {h.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            ) : (
              <Input
                id="leave-start"
                type="date"
                value={startDate}
                min={today()}
                onChange={(e) => setStartDate(e.target.value)}
              />
            )}
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="leave-end">Last day</Label>
            <Input
              id="leave-end"
              type="date"
              value={effectiveEnd}
              min={startDate || today()}
              disabled={type === "exchange"}
              onChange={(e) => setEndDate(e.target.value)}
            />
            {type === "exchange" && (
              <p className="text-xs text-slate-400">
                An exchange is always a single day.
              </p>
            )}
          </div>
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="leave-reason">Reason</Label>
          <Textarea
            id="leave-reason"
            rows={2}
            value={reason}
            placeholder="Optional, but it helps your manager decide."
            onChange={(e) => setReason(e.target.value)}
          />
        </div>

        {/* Live hours breakdown */}
        {breakdown && type !== "exchange" && (
          <div className="rounded-lg bg-slate-50 border border-slate-200 p-3.5 text-sm">
            <p className="font-medium text-slate-900 tabular-nums">
              {breakdown.hours}h · {breakdown.workdays.length} working{" "}
              {breakdown.workdays.length === 1 ? "day" : "days"}
            </p>
            {breakdown.skipped.length > 0 && (
              <ul className="mt-2 space-y-0.5 text-xs text-slate-500">
                {breakdown.skipped.map((s) => (
                  <li key={s.date}>
                    {s.date} —{" "}
                    {s.reason === "holiday"
                      ? `${s.holidayName} (company holiday)`
                      : "weekend"}
                    , not deducted
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}

        {type === "exchange" && startDate && (
          <div className="rounded-lg bg-slate-50 border border-slate-200 p-3.5 text-sm text-slate-700">
            Working this holiday adds <strong>8h</strong> to your balance.
          </div>
        )}

        {type === "sick" && breakdown && (
          <div className="flex items-start gap-2 text-sm text-slate-600">
            <Info size={15} className="mt-0.5 shrink-0 text-slate-400" />
            <p>
              {breakdown.hours <= SICK_AUTO_APPROVE_HOURS
                ? "Approved immediately — sick leave of three days or less does not wait on your manager. It does not reduce your balance."
                : "Longer than three days, so this goes to your manager. It still does not reduce your balance."}
            </p>
          </div>
        )}

        {error && (
          <div className="flex items-start gap-2 rounded-lg bg-rose-50 border border-rose-200 p-3 text-sm text-rose-800">
            <X size={15} className="mt-0.5 shrink-0" />
            <p>{error}</p>
          </div>
        )}

        {!error &&
          warnings.map((w) => (
            <div
              key={w.key}
              className="flex items-start gap-2 rounded-lg bg-amber-50 border border-amber-200 p-3 text-sm text-amber-900"
            >
              <AlertTriangle size={15} className="mt-0.5 shrink-0" />
              <p>{w.text}</p>
            </div>
          ))}

        <div className="flex items-center gap-3 pt-1">
          <Button onClick={submit} disabled={!canSubmit}>
            Submit request
          </Button>
          {canSubmit && isAutoApproved(draft) && (
            <span className="text-xs text-emerald-700 flex items-center gap-1">
              <Check size={13} /> Takes effect immediately
            </span>
          )}
        </div>
      </Card>

      {/* My requests */}
      <Card className="p-5">
        <h2 className="text-sm font-semibold text-slate-900 mb-3">
          My requests
        </h2>
        {requests.length === 0 ? (
          <p className="text-sm text-slate-400">Nothing submitted yet.</p>
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
        <div className="flex items-baseline justify-between mt-3 pt-3 border-t border-slate-200">
          <span className="text-sm font-medium text-slate-900">Balance</span>
          <span className="text-sm font-semibold tabular-nums text-slate-900">
            {balance.toFixed(2)}h
          </span>
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
          {upcomingHolidays.map((h) => (
            <li
              key={h.date}
              className="py-2 flex items-center justify-between text-sm"
            >
              <span className="text-slate-700">
                <span className="tabular-nums text-slate-500 mr-3">
                  {h.date}
                </span>
                {h.name}
              </span>
              {h.exchangeable && (
                <Badge variant="outline" className="text-xs">
                  Exchangeable
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
