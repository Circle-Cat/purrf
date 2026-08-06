/**
 * Leave calculation helpers for the prototype.
 *
 * One definition of "working day" is shared by deduction, advance-notice, and
 * the sick-leave auto-approval threshold — the spec is explicit that a second
 * definition must never be introduced, and the prototype mirrors that so the
 * demo cannot drift from the design it is illustrating.
 */

import {
  COMPANY_HOLIDAYS,
  HOURS_PER_DAY,
  SICK_AUTO_APPROVE_HOURS,
  WEEKEND_DAYS,
} from "@/pages/LeavePrototype/mockData";

const HOLIDAY_BY_DATE = new Map(COMPANY_HOLIDAYS.map((h) => [h.date, h]));

/**
 * Format a Date as an ISO calendar date in local time.
 *
 * `toISOString()` would shift the day for anyone west of UTC, which silently
 * moves leave onto the wrong date.
 *
 * @param {Date} date
 * @returns {string} e.g. "2026-10-15"
 */
export const toISODate = (date) => {
  const month = `${date.getMonth() + 1}`.padStart(2, "0");
  const day = `${date.getDate()}`.padStart(2, "0");
  return `${date.getFullYear()}-${month}-${day}`;
};

/**
 * Parse an ISO calendar date into a local-midnight Date.
 *
 * @param {string} iso
 * @returns {Date}
 */
export const fromISODate = (iso) => {
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(y, m - 1, d);
};

/** Today, as an ISO calendar date. */
export const today = () => toISODate(new Date());

/**
 * Classify a single date.
 *
 * @param {string} iso
 * @returns {{isWorkday: boolean, reason: string|null, holidayName: string|null}}
 */
export const classifyDay = (iso) => {
  const holiday = HOLIDAY_BY_DATE.get(iso);
  if (holiday) {
    return {
      isWorkday: false,
      reason: "holiday",
      holidayName: holiday.name,
    };
  }
  if (WEEKEND_DAYS.includes(fromISODate(iso).getDay())) {
    return { isWorkday: false, reason: "weekend", holidayName: null };
  }
  return { isWorkday: true, reason: null, holidayName: null };
};

/**
 * Every calendar date from `startISO` to `endISO`, inclusive.
 *
 * @param {string} startISO
 * @param {string} endISO
 * @returns {string[]}
 */
export const datesBetween = (startISO, endISO) => {
  const out = [];
  const end = fromISODate(endISO);
  for (let d = fromISODate(startISO); d <= end; d.setDate(d.getDate() + 1)) {
    out.push(toISODate(d));
  }
  return out;
};

/**
 * Break a requested range into the days that are deducted and the days that
 * are not, so the form can show its work rather than just a total.
 *
 * @param {string} startISO
 * @param {string} endISO
 * @returns {{hours: number, workdays: string[], skipped: Array<{date: string, reason: string, holidayName: string|null}>}}
 */
export const breakdownRange = (startISO, endISO) => {
  const workdays = [];
  const skipped = [];
  for (const iso of datesBetween(startISO, endISO)) {
    const { isWorkday, reason, holidayName } = classifyDay(iso);
    if (isWorkday) {
      workdays.push(iso);
    } else {
      skipped.push({ date: iso, reason, holidayName });
    }
  }
  return { hours: workdays.length * HOURS_PER_DAY, workdays, skipped };
};

/**
 * Hours between two "HH:MM" times, to two decimals.
 *
 * Only meaningful for a single-day request: a range spanning more than one day
 * is whole days by definition, since there is no way to say "the afternoon of
 * the first day and the morning of the last" with one pair of times.
 *
 * @param {string} from - "09:30"
 * @param {string} to - "13:00"
 * @returns {number} hours, 0 if the pair does not make sense
 */
export const hoursBetweenTimes = (from, to) => {
  if (!from || !to) return 0;
  const [fh, fm] = from.split(":").map(Number);
  const [th, tm] = to.split(":").map(Number);
  const minutes = th * 60 + tm - (fh * 60 + fm);
  return minutes <= 0 ? 0 : Math.round((minutes / 60) * 100) / 100;
};

/**
 * Count working days in the half-open interval [fromISO, toISO).
 *
 * The submission day counts, the first day of leave does not — the boundary
 * the spec settled on.
 *
 * @param {string} fromISO
 * @param {string} toISO
 * @returns {number}
 */
export const workdaysBefore = (fromISO, toISO) => {
  if (fromISO >= toISO) return 0;
  return datesBetween(fromISO, toISO).filter(
    (iso) => iso < toISO && classifyDay(iso).isWorkday,
  ).length;
};

/**
 * Advance notice check: requesting n days requires 2n working days of notice.
 *
 * @param {number} hours
 * @param {string} startISO
 * @param {string} submitISO
 * @returns {{required: number, actual: number, ok: boolean}}
 */
export const advanceNotice = (hours, startISO, submitISO) => {
  const days = Math.ceil(hours / HOURS_PER_DAY);
  const required = 2 * days;
  const actual = workdaysBefore(submitISO, startISO);
  return { required, actual, ok: actual >= required };
};

/**
 * Sum a ledger. Every entry type counts toward the balance — the accrual
 * engine's "already granted" total excludes hand-written rows, but that is a
 * different sum and never touches this one.
 *
 * @param {Array<{hours: number}>} ledger
 * @returns {number}
 */
export const ledgerBalance = (ledger) =>
  Math.round(ledger.reduce((sum, row) => sum + row.hours, 0) * 100) / 100;

/**
 * Hours reserved by requests that are submitted but not yet decided. Only paid
 * leave reserves — sick leave has no entitlement and exchange adds rather than
 * spends.
 *
 * @param {Array<{type: string, status: string, hours: number}>} requests
 * @returns {number}
 */
export const pendingReserved = (requests) =>
  requests
    .filter((r) => r.type === "paid" && r.status === "pending")
    .reduce((sum, r) => sum + r.hours, 0);

/**
 * Whether two inclusive date ranges share any day.
 *
 * @param {string} aStart
 * @param {string} aEnd
 * @param {string} bStart
 * @param {string} bEnd
 * @returns {boolean}
 */
export const rangesOverlap = (aStart, aEnd, bStart, bEnd) =>
  aStart <= bEnd && bStart <= aEnd;

/**
 * Validate a draft request against every submission rule, returning the first
 * blocking error plus any non-blocking warnings.
 *
 * @param {object} draft - {type, startDate, endDate, hours}
 * @param {Array<object>} existingRequests - the requester's own requests
 * @param {number} available - balance minus pending reservations
 * @returns {{error: string|null, warnings: Array<{key: string, text: string}>}}
 */
export const validateDraft = (draft, existingRequests, available) => {
  const { type, startDate, endDate, hours } = draft;
  const warnings = [];

  if (!startDate || !endDate) {
    return { error: "Pick a start and end date.", warnings };
  }
  if (endDate < startDate) {
    return { error: "The end date is before the start date.", warnings };
  }
  if (startDate < today()) {
    return {
      error:
        "Leave cannot start in the past. Ask an administrator to adjust your balance instead.",
      warnings,
    };
  }
  // Checked before the empty-range case on purpose. Asking for a day you have
  // already agreed to work is an overlap, and saying so names the request to
  // cancel; falling through to "that day is a company holiday" would be true
  // but useless to someone who just traded it away.
  const clash = existingRequests.find(
    (r) =>
      ["pending", "approved", "cancel_pending"].includes(r.status) &&
      rangesOverlap(startDate, endDate, r.startDate, r.endDate),
  );
  if (clash) {
    return {
      error: `This overlaps request #${clash.id} (${clash.startDate} → ${clash.endDate}).`,
      warnings,
    };
  }

  if (hours === 0) {
    return {
      error: "Every day in this range is a weekend or a company holiday.",
      warnings,
    };
  }

  if (type === "exchange") {
    // All-or-nothing: one ineligible day rejects the request rather than being
    // quietly dropped, so nobody discovers after the fact that they worked a
    // day they were never credited for.
    const ineligible = datesBetween(startDate, endDate).filter(
      (date) => !HOLIDAY_BY_DATE.get(date)?.exchangeable,
    );
    if (ineligible.length > 0) {
      const shown = ineligible.slice(0, 3).join(", ");
      const rest =
        ineligible.length > 3 ? ` and ${ineligible.length - 3} more` : "";
      return {
        error: `Not exchangeable: ${shown}${rest}. Every day in the range has to be an exchangeable company holiday.`,
        warnings,
      };
    }
    const notice = advanceNotice(hours, startDate, today());
    if (!notice.ok) {
      return {
        error: `Exchange needs ${notice.required} working days of notice; this has ${notice.actual}.`,
        warnings,
      };
    }
  }

  if (type === "paid") {
    const notice = advanceNotice(hours, startDate, today());
    if (!notice.ok) {
      warnings.push({
        key: "late",
        text: `Short notice: ${notice.required} working days expected, ${notice.actual} given. Your manager will see this flagged.`,
      });
    }
    if (hours > available) {
      warnings.push({
        key: "overdraft",
        text: `This exceeds your balance. Approving it puts you at ${(available - hours).toFixed(2)}h.`,
      });
    }
  }

  return { error: null, warnings };
};

/**
 * Whether a sick request is short enough to skip manager approval.
 *
 * @param {object} draft - {type, hours}
 * @returns {boolean}
 */
export const isAutoApproved = (draft) =>
  draft.type === "sick" && draft.hours <= SICK_AUTO_APPROVE_HOURS;

/** Display label for each request type. */
export const TYPE_LABEL = {
  paid: "Paid leave",
  sick: "Sick leave",
  exchange: "Holiday exchange",
};

/**
 * Merge holiday date rows into display segments.
 *
 * Holidays are stored one row per date, so a five-day break is five rows. Shown
 * raw that is five identical-looking lines; shown as a start/end pair it is one.
 * Rows join a segment only when they share a name *and* run consecutively, so a
 * break split across a working day stays two segments — which is how the real
 * calendar is actually written.
 *
 * Exchangeability is per date, so a segment reports how many of its days
 * qualify rather than a single flag.
 *
 * @param {Array<{date: string, name: string, exchangeable: boolean}>} holidays
 * @returns {Array<{name: string, start: string, end: string, days: number, exchangeableDays: number, dates: string[]}>}
 */
export const groupHolidays = (holidays) => {
  const sorted = [...holidays].sort((a, b) => a.date.localeCompare(b.date));
  const segments = [];

  for (const row of sorted) {
    const last = segments[segments.length - 1];
    const dayAfterLast = last
      ? toISODate(
          new Date(
            fromISODate(last.end).setDate(fromISODate(last.end).getDate() + 1),
          ),
        )
      : null;

    if (last && last.name === row.name && dayAfterLast === row.date) {
      last.end = row.date;
      last.days += 1;
      last.dates.push(row.date);
      if (row.exchangeable) last.exchangeableDays += 1;
    } else {
      segments.push({
        name: row.name,
        start: row.date,
        end: row.date,
        days: 1,
        exchangeableDays: row.exchangeable ? 1 : 0,
        dates: [row.date],
      });
    }
  }

  return segments;
};

/**
 * Display label for each ledger entry type.
 *
 * The balance card shows three numbers and does not try to explain how the
 * balance got there; this is where that question is answered instead.
 */
export const ENTRY_LABEL = {
  weekly_accrual: "Weekly accrual",
  holiday_grant: "Public holiday grant",
  leave_deduction: "Leave taken",
  exchange_credit: "Holiday worked",
  manual_adjustment: "Adjustment by administrator",
  reversal: "Reversal",
  carryover_forfeit: "Carry-over cap",
};

/** Display label for each request status. */
export const STATUS_LABEL = {
  pending: "Pending",
  approved: "Approved",
  rejected: "Rejected",
  withdrawn: "Withdrawn",
  cancel_pending: "Cancellation pending",
  cancelled: "Cancelled",
};
