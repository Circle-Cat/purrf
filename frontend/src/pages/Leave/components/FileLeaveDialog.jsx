import { useState } from "react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  LEAVE_REQUEST_TYPE,
  LEAVE_TYPE_LABELS,
} from "@/constants/LeaveRequest";
import RequestSpan from "@/pages/Leave/components/RequestSpan";
import { useLeaveRequestPreview } from "@/pages/Leave/hooks/useLeaveRequestPreview";

const EMPTY = {
  type: LEAVE_REQUEST_TYPE.PAID,
  startDate: "",
  endDate: "",
  startTime: "",
  endTime: "",
  reason: "",
};

/**
 * Every time a part day may start or end at: the server takes leave in
 * half-hour steps and refuses anything else, so nothing else is offered.
 * "HH:MM", the shape the request sends.
 */
const HALF_HOURS = Array.from({ length: 48 }, (_, index) => {
  const hour = String(Math.floor(index / 2)).padStart(2, "0");
  return `${hour}:${index % 2 ? "30" : "00"}`;
});

/**
 * Whether this request can carry clock times.
 *
 * Only a single day of leave can. A range is always whole days and an exchange
 * is always whole days, and the server refuses times anywhere else rather than
 * ignoring them -- so the fields are not offered where they cannot be sent.
 */
const takesTimes = (form) =>
  form.type !== LEAVE_REQUEST_TYPE.EXCHANGE &&
  Boolean(form.startDate) &&
  form.startDate === form.endDate;

/**
 * What is wrong with the form on its own terms, or null.
 *
 * Deliberately shallow. Overlapping requests, dates in the past, a year with
 * no calendar entered, notice that falls short, an exchange touching a day
 * that cannot be traded -- all of that is decided by the server and shown in
 * its own words. Repeating those rules here would be a second implementation
 * free to disagree with the one that actually refuses.
 *
 * Dates compare as strings. They are `YYYY-MM-DD`, which sorts correctly, and
 * building a Date to compare them is how `2026-10-01` becomes 30 September
 * west of UTC.
 */
const structuralProblem = (form) => {
  if (!form.startDate || !form.endDate) return "Pick both dates.";
  if (form.endDate < form.startDate) {
    return "The last day cannot come before the first.";
  }
  if (takesTimes(form) && Boolean(form.startTime) !== Boolean(form.endTime)) {
    return "Give both times, or neither.";
  }
  if (takesTimes(form) && form.startTime && form.endTime <= form.startTime) {
    return "The end time has to come after the start time.";
  }
  return null;
};

/**
 * FileLeaveDialog
 *
 * Files one request. Native date and time inputs on purpose: their values are
 * already the `YYYY-MM-DD` and `HH:MM` strings the API takes, so nothing here
 * has to construct a Date, and a native control needs no pointer events to be
 * driven in a test.
 *
 * The hours the days come to are asked of the server as soon as the dates
 * make sense, and shown above Submit with the working days and the days off
 * the range skips. They are never worked out here: the count skips company
 * holidays and the weekend, and a second implementation in the browser would
 * quote a figure the ledger then contradicts. When the dates cannot be filed
 * the server's reason shows instead, before anything is submitted.
 *
 * Who will read the request is said above Submit, from the same lookup filing
 * makes. When nobody can approve it, the reason is shown instead and Submit is
 * off: filing would only be refused with that same reason.
 *
 * @param {{
 *   isOpen: boolean,
 *   isSaving: boolean,
 *   saveError: string|null,
 *   onClose: () => void,
 *   onSubmit: (payload: object) => Promise<boolean>,
 *   approverName?: string|null,
 *   approverLdap?: string|null,
 *   approverProblem?: string|null,
 * }} props
 */
const FileLeaveDialog = ({
  isOpen,
  isSaving,
  saveError,
  onClose,
  onSubmit,
  approverName = null,
  approverLdap = null,
  approverProblem = null,
}) => {
  const [form, setForm] = useState(EMPTY);
  const [problem, setProblem] = useState(null);
  // The refusal lives in the hook the parent shares and outlives this dialog,
  // so it is shown only for a submit made since the dialog was opened.
  const [hasSubmitted, setHasSubmitted] = useState(false);

  const withTimes = takesTimes(form) && form.startTime && form.endTime;
  const payload =
    isOpen && !structuralProblem(form)
      ? {
          type: form.type,
          startDate: form.startDate,
          endDate: form.endDate,
          startTime: withTimes ? form.startTime : null,
          endTime: withTimes ? form.endTime : null,
        }
      : null;
  const { preview, previewError } = useLeaveRequestPreview(payload);

  // Changing what is being asked for retires the refusal of the last submit:
  // it was about other dates, and the preview now speaks for these ones.
  const set = (field) => (event) => {
    if (field !== "reason") setHasSubmitted(false);
    setForm((prev) => ({ ...prev, [field]: event.target.value }));
  };

  const close = () => {
    setForm(EMPTY);
    setProblem(null);
    setHasSubmitted(false);
    onClose();
  };

  const submit = async () => {
    const found = structuralProblem(form);
    setProblem(found);
    if (found) return;

    setHasSubmitted(true);
    const saved = await onSubmit({
      type: form.type,
      startDate: form.startDate,
      endDate: form.endDate,
      startTime: withTimes ? form.startTime : null,
      endTime: withTimes ? form.endTime : null,
      reason: form.reason.trim() || null,
    });
    if (saved) close();
  };

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && close()}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Request leave</DialogTitle>
        </DialogHeader>

        <div className="space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor="leave-type">Type</Label>
            <select
              id="leave-type"
              className="h-9 w-full rounded-md border border-input bg-transparent px-3 text-sm"
              value={form.type}
              onChange={set("type")}
            >
              {Object.values(LEAVE_REQUEST_TYPE).map((type) => (
                <option key={type} value={type}>
                  {LEAVE_TYPE_LABELS[type]}
                </option>
              ))}
            </select>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label htmlFor="leave-start-date">First day</Label>
              <Input
                id="leave-start-date"
                type="date"
                value={form.startDate}
                onChange={set("startDate")}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="leave-end-date">Last day</Label>
              <Input
                id="leave-end-date"
                type="date"
                value={form.endDate}
                onChange={set("endDate")}
              />
            </div>
          </div>

          {takesTimes(form) && (
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label htmlFor="leave-start-time">From (optional)</Label>
                <select
                  id="leave-start-time"
                  className="h-9 w-full rounded-md border border-input bg-transparent px-3 text-sm"
                  value={form.startTime}
                  onChange={set("startTime")}
                >
                  <option value="">—</option>
                  {HALF_HOURS.map((time) => (
                    <option key={time} value={time}>
                      {time}
                    </option>
                  ))}
                </select>
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="leave-end-time">To (optional)</Label>
                <select
                  id="leave-end-time"
                  className="h-9 w-full rounded-md border border-input bg-transparent px-3 text-sm"
                  value={form.endTime}
                  onChange={set("endTime")}
                >
                  <option value="">—</option>
                  {HALF_HOURS.map((time) => (
                    <option key={time} value={time}>
                      {time}
                    </option>
                  ))}
                </select>
              </div>
            </div>
          )}

          <div className="space-y-1.5">
            <Label htmlFor="leave-reason">Reason (optional)</Label>
            <Textarea
              id="leave-reason"
              value={form.reason}
              onChange={set("reason")}
              rows={3}
            />
          </div>

          {preview && payload && (
            <RequestSpan row={{ ...payload, ...preview }} />
          )}
          {preview?.isLateNotice && (
            <p className="text-sm text-amber-700">
              {`Less than ${preview.requiredNoticeWorkdays} working days' notice. Your manager will see it marked as short notice.`}
            </p>
          )}
          {previewError && !(hasSubmitted && saveError) && (
            <p className="text-sm text-red-700">{previewError}</p>
          )}

          {approverProblem ? (
            <p className="text-sm text-red-700">{approverProblem}</p>
          ) : (
            (approverName || approverLdap) && (
              <p className="text-sm text-muted-foreground">
                {`Your request goes to ${
                  approverName && approverLdap
                    ? `${approverName} (${approverLdap})`
                    : approverName || approverLdap
                } for approval.`}
              </p>
            )
          )}

          {problem && <p className="text-sm text-red-700">{problem}</p>}
          {/* The server's own wording: each refusal names the fix, and a
              generic message would throw that away. */}
          {hasSubmitted && saveError && (
            <p className="text-sm text-red-700">{saveError}</p>
          )}
        </div>

        <DialogFooter>
          <Button variant="outline" disabled={isSaving} onClick={close}>
            Cancel
          </Button>
          <Button
            disabled={isSaving || Boolean(approverProblem)}
            onClick={submit}
          >
            {isSaving ? "Submitting…" : "Submit"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export default FileLeaveDialog;
