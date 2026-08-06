import { useMemo } from "react";
import { AlertOctagon, Database } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { groupHolidays, segmentGrants } from "@/pages/LeavePrototype/leaveCalc";

/**
 * A read-only list of holiday periods.
 *
 * @param {object} props
 * @param {string} props.title
 * @param {string} props.blurb
 * @param {Array<object>} props.segments
 * @param {(segment: object) => string|null} [props.annotate]
 * @param {string} [props.footnote]
 * @returns {JSX.Element}
 */
const PeriodList = ({ title, blurb, segments, annotate, footnote }) => (
  <Card className="p-5 space-y-3">
    <div>
      <h3 className="text-sm font-semibold text-slate-900">{title}</h3>
      <p className="text-xs text-slate-500 mt-0.5">{blurb}</p>
    </div>

    {segments.length === 0 ? (
      <p className="py-6 text-center text-sm text-slate-400">
        Nothing loaded for this year.
      </p>
    ) : (
      <ul className="divide-y divide-slate-100">
        {segments.map((s) => (
          <li
            key={`${s.name}-${s.start}`}
            className="py-2 flex items-center justify-between gap-3"
          >
            <div className="min-w-0">
              <span className="text-sm text-slate-800">{s.name}</span>
              <span className="text-xs text-slate-500 ml-2 tabular-nums">
                {s.days === 1 ? s.start : `${s.start} – ${s.end}`}
              </span>
              <span className="text-xs text-slate-400 ml-2">{s.days}d</span>
            </div>
            <div className="flex items-center gap-2 shrink-0">
              {annotate && (
                <span className="text-sm tabular-nums font-medium text-slate-700">
                  {annotate(s)}
                </span>
              )}
              {s.exchangeableDays > 0 && (
                <Badge variant="outline" className="text-xs">
                  {s.exchangeableDays === s.days
                    ? "Exchangeable"
                    : `${s.exchangeableDays}/${s.days}`}
                </Badge>
              )}
            </div>
          </li>
        ))}
      </ul>
    )}

    <div className="flex items-baseline justify-between gap-3 pt-1 border-t border-slate-100 text-xs text-slate-400 tabular-nums">
      <span>
        {segments.length} periods · {segments.reduce((n, s) => n + s.days, 0)}{" "}
        days
      </span>
      {footnote && <span>{footnote}</span>}
    </div>
  </Card>
);

/**
 * CalendarAdmin
 *
 * Both calendars, read-only. They are written straight to the database once a
 * year, so there is nothing to edit here — but there does have to be somewhere
 * to look, for two reasons.
 *
 * A mistake in the statutory list cannot be caught anywhere else. Its days are
 * the denominator of every conversion payout, so a missing one re-prices every
 * period while the annual total still comes to exactly the entitlement — the
 * year is divided out of it, not summed from the days. The periods and payouts
 * shown here are the only place that is visible.
 *
 * And a year with no calendar at all blocks every request dated inside it, so
 * next year's absence is called out well before anyone runs into it.
 *
 * @param {object} props
 * @param {Array<object>} props.company
 * @param {Array<object>} props.statutory
 * @param {number} props.conversionHours
 * @returns {JSX.Element}
 */
const CalendarAdmin = ({ company, statutory, conversionHours }) => {
  const companySegments = useMemo(() => groupHolidays(company), [company]);
  const grants = useMemo(
    () => segmentGrants(statutory, conversionHours),
    [statutory, conversionHours],
  );
  const statutorySegments = useMemo(
    () => groupHolidays(statutory),
    [statutory],
  );

  const hoursByPeriod = useMemo(
    () => new Map(grants.periods.map((p) => [`${p.name}-${p.start}`, p.hours])),
    [grants],
  );

  /** Years that have anything loaded at all. */
  const loadedYears = useMemo(() => {
    const years = new Set();
    for (const r of [...company, ...statutory]) years.add(r.date.slice(0, 4));
    return years;
  }, [company, statutory]);

  const nextYear = String(new Date().getFullYear() + 1);
  const nextYearMissing = !loadedYears.has(nextYear);

  return (
    <div className="space-y-4">
      {nextYearMissing && (
        <Card className="p-4 border-l-4 border-l-rose-500">
          <div className="flex items-start gap-2.5">
            <AlertOctagon size={16} className="mt-0.5 shrink-0 text-rose-500" />
            <div>
              <h3 className="text-sm font-semibold text-slate-900">
                No calendar loaded for {nextYear}
              </h3>
              <p className="text-xs text-slate-500 mt-0.5">
                Every request dated in {nextYear} will be refused until it is,
                and no conversion hours will be paid out that year. The
                government publishes its dates the November before.
              </p>
            </div>
          </div>
        </Card>
      )}

      <div className="flex items-start gap-2 text-xs text-slate-500">
        <Database size={14} className="mt-0.5 shrink-0" />
        <p>
          Loaded straight into the database once a year, so there is nothing to
          edit here. Check what arrived against the published announcement — a
          missing statutory day re-prices every period below and still totals{" "}
          {conversionHours.toFixed(2)}h, so nothing else will flag it.
        </p>
      </div>

      <PeriodList
        title="Company holidays"
        blurb="Office closed. Never deducted from anyone's leave, and no effect on what anyone is paid."
        segments={companySegments}
      />

      <PeriodList
        title="Statutory holidays"
        blurb="Each period pays its share of the conversion entitlement on its first day. No effect on whether a leave day is deducted."
        segments={statutorySegments}
        annotate={(s) => {
          const hours = hoursByPeriod.get(`${s.name}-${s.start}`);
          return hours === undefined ? null : `${hours.toFixed(2)}h`;
        }}
        footnote={`pays ${grants.totalHours.toFixed(2)}h`}
      />
    </div>
  );
};

export default CalendarAdmin;
