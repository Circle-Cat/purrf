import { useMemo } from "react";
import HolidayEditor from "@/pages/LeavePrototype/HolidayEditor";
import { segmentGrants } from "@/pages/LeavePrototype/leaveCalc";

/**
 * CalendarAdmin
 *
 * The once-a-year job: type in next year's two calendars.
 *
 * What each statutory period pays is shown on the period itself rather than in
 * a table of its own. A separate table repeated the periods, the dates and the
 * day counts that the list above it already showed, and the one figure it
 * added — the hours — is the one thing an administrator cannot check against
 * anything, since the government announcement does not mention it.
 *
 * What they can check is the period breakdown against that announcement, and
 * that has to be checked, because a missing day cannot be caught downstream:
 * the annual total is divided out of the entitlement rather than summed from
 * the days, so it comes out right no matter what is typed.
 *
 * @param {object} props
 * @param {Array<object>} props.company
 * @param {Array<object>} props.statutory
 * @param {number} props.conversionHours
 * @param {(rows: Array<object>) => void} props.onCompanyChange
 * @param {(rows: Array<object>) => void} props.onStatutoryChange
 * @returns {JSX.Element}
 */
const CalendarAdmin = ({
  company,
  statutory,
  conversionHours,
  onCompanyChange,
  onStatutoryChange,
}) => {
  const grants = useMemo(
    () => segmentGrants(statutory, conversionHours),
    [statutory, conversionHours],
  );

  const hoursByPeriod = useMemo(
    () => new Map(grants.periods.map((p) => [`${p.name}-${p.start}`, p.hours])),
    [grants],
  );

  return (
    <div className="space-y-4">
      <HolidayEditor
        title="Company holidays"
        blurb="Office closed. Never deducted from anyone's leave, and no effect on what anyone is paid."
        rows={company}
        withExchangeable
        onChange={onCompanyChange}
      />

      <HolidayEditor
        title="Statutory holidays"
        blurb="Each period pays its share of the conversion entitlement on its first day. No effect on whether a leave day is deducted."
        rows={statutory}
        withExchangeable={false}
        onChange={onStatutoryChange}
        annotate={(s) => {
          const hours = hoursByPeriod.get(`${s.name}-${s.start}`);
          return hours === undefined ? null : `${hours.toFixed(2)}h`;
        }}
        footnote={`pays ${grants.totalHours.toFixed(2)}h`}
      />

      <p className="text-xs text-slate-500">
        Check the statutory periods against the published announcement before
        saving. A missing day still totals {conversionHours.toFixed(2)}h — the
        year is divided out of the entitlement, not added up from the days — so
        it will not show up anywhere else.
      </p>
    </div>
  );
};

export default CalendarAdmin;
