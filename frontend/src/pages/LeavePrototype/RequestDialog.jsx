import { useMemo, useState } from "react";
import { AlertTriangle, Check, Info, UserCheck, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { SICK_AUTO_APPROVE_HOURS } from "@/pages/LeavePrototype/mockData";
import {
  breakdownRange,
  datesBetween,
  isAutoApproved,
  today,
  validateDraft,
} from "@/pages/LeavePrototype/leaveCalc";

/**
 * RequestDialog
 *
 * The request form, in a dialog. It computes hours as you pick dates and shows
 * which days it skipped and why — "I asked for five days and it says sixteen
 * hours" is the first question anyone asks, and answering it before submission
 * is cheaper than answering it afterwards.
 *
 * Every field resets when the dialog closes: a half-filled request left over
 * from last time is never what someone wants next time.
 *
 * @param {object} props
 * @param {boolean} props.open
 * @param {(open: boolean) => void} props.onOpenChange
 * @param {Array<object>} props.requests - the requester's own requests, for clash detection
 * @param {number} props.available - balance minus pending reservations
 * @param {Array<{date: string, segment: object}>} props.exchangeableDays
 * @param {string} props.approverName - who this request will go to
 * @param {(draft: object) => void} props.onSubmit
 * @returns {JSX.Element}
 */
const RequestDialog = ({
  open,
  onOpenChange,
  requests,
  available,
  exchangeableDays,
  approverName,
  onSubmit,
}) => {
  const [type, setType] = useState("paid");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [reason, setReason] = useState("");

  const reset = () => {
    setType("paid");
    setStartDate("");
    setEndDate("");
    setReason("");
  };

  const close = (next) => {
    if (!next) reset();
    onOpenChange(next);
  };

  /** An unset end date means a single day, whatever the type. */
  const effectiveEnd = endDate || startDate;

  const breakdown = useMemo(
    () =>
      startDate && effectiveEnd && effectiveEnd >= startDate
        ? breakdownRange(startDate, effectiveEnd)
        : null,
    [startDate, effectiveEnd],
  );

  /**
   * Exchange credits every day in the range, because they must all be
   * exchangeable holidays for it to submit at all — there is nothing to skip.
   * Leave does the opposite and only counts working days.
   */
  const exchangeDays =
    startDate && effectiveEnd >= startDate
      ? datesBetween(startDate, effectiveEnd).length
      : 0;

  const draft = {
    type,
    startDate,
    endDate: effectiveEnd,
    hours: type === "exchange" ? exchangeDays * 8 : (breakdown?.hours ?? 0),
  };

  const { error, warnings } = startDate
    ? validateDraft(draft, requests, available)
    : { error: null, warnings: [] };

  const canSubmit = Boolean(startDate && effectiveEnd) && !error;

  const submit = () => {
    if (!canSubmit) return;
    onSubmit({ ...draft, reason });
    reset();
    onOpenChange(false);
  };

  return (
    <Dialog open={open} onOpenChange={close}>
      <DialogContent className="sm:max-w-xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Request time off</DialogTitle>
          <DialogDescription>
            Hours are worked out from the dates — weekends and company holidays
            are never deducted.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-1">
          <div className="grid sm:grid-cols-3 gap-4">
            <div className="space-y-1.5">
              <Label htmlFor="leave-type">Type</Label>
              <Select
                value={type}
                onValueChange={(next) => {
                  // Dates carried across a type change are almost always wrong
                  // — an exchange only accepts holidays, leave only accepts
                  // non-holidays.
                  setType(next);
                  setStartDate("");
                  setEndDate("");
                }}
              >
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
                    {exchangeableDays.map(({ date, segment }) => (
                      <SelectItem key={date} value={date}>
                        {date} · {segment.name}
                        {segment.days > 1 &&
                          ` (${segment.start} – ${segment.end})`}
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
              {type === "exchange" ? (
                <Select value={endDate} onValueChange={setEndDate}>
                  <SelectTrigger id="leave-end">
                    <SelectValue placeholder="Same day" />
                  </SelectTrigger>
                  <SelectContent>
                    {exchangeableDays
                      .filter(({ date }) => !startDate || date >= startDate)
                      .map(({ date, segment }) => (
                        <SelectItem key={date} value={date}>
                          {date} · {segment.name}
                        </SelectItem>
                      ))}
                  </SelectContent>
                </Select>
              ) : (
                <Input
                  id="leave-end"
                  type="date"
                  value={effectiveEnd}
                  min={startDate || today()}
                  onChange={(e) => setEndDate(e.target.value)}
                />
              )}
              {type === "exchange" && (
                <p className="text-xs text-slate-400">
                  Leave blank to work just one day.
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

          {type === "exchange" && startDate && exchangeDays > 0 && (
            <div className="rounded-lg bg-slate-50 border border-slate-200 p-3.5 text-sm text-slate-700">
              Working{" "}
              {exchangeDays === 1
                ? "this holiday"
                : `${exchangeDays} holiday days`}{" "}
              adds <strong>{exchangeDays * 8}h</strong> to your balance.
              {exchangeDays > 1 && (
                <p className="text-xs text-slate-500 mt-1">
                  The rest of the break stays yours — you only trade the days
                  you pick here.
                </p>
              )}
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

          {/* Who acts on this. The approver is snapshotted when the request is
              submitted, not looked up later, so naming them here is what will
              actually be recorded. */}
          {startDate && !error && (
            <div className="flex items-start gap-2 rounded-lg border border-slate-200 p-3 text-sm">
              {isAutoApproved(draft) ? (
                <>
                  <Check
                    size={15}
                    className="mt-0.5 shrink-0 text-emerald-600"
                  />
                  <p className="text-slate-700">
                    Approved on submission — nobody has to action it.{" "}
                    <strong className="font-medium">{approverName}</strong>{" "}
                    still sees it in their list.
                  </p>
                </>
              ) : (
                <>
                  <UserCheck
                    size={15}
                    className="mt-0.5 shrink-0 text-slate-400"
                  />
                  <p className="text-slate-700">
                    Goes to{" "}
                    <strong className="font-medium">{approverName}</strong> for
                    approval.
                  </p>
                </>
              )}
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
        </div>

        <DialogFooter className="gap-2">
          <Button variant="outline" onClick={() => close(false)}>
            Cancel
          </Button>
          <Button onClick={submit} disabled={!canSubmit}>
            Submit request
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export default RequestDialog;
