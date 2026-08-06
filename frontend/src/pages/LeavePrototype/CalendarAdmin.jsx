import { useMemo } from "react";
import HolidayEditor from "@/pages/LeavePrototype/HolidayEditor";
import { segmentGrants } from "@/pages/LeavePrototype/leaveCalc";

/**
 * CalendarAdmin
 *
 * The once-a-year job: type in next year's two calendars.
 *
 * The payout table sits inside the statutory card rather than under both,
 * because it is derived from the statutory list alone. Which list drives
 * payouts and which drives deductions is the pair this design is most often
 * confused about, and a table floating between them invites exactly that.
 *
 * That table is also the only check on the statutory list. Its days are the
 * denominator of every payout, so missing one does not fail — the annual total
 * is divided out of the entitlement, not summed from the days, so it still
 * comes to the right number while every period beneath it has been re-priced.
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
        blurb="Sets when conversion hours are paid out. No effect on whether a leave day is deducted."
        rows={statutory}
        withExchangeable={false}
        onChange={onStatutoryChange}
      >
        <div className="pt-4 border-t border-slate-200">
          <div className="flex items-start justify-between gap-4 mb-3">
            <div>
              <h4 className="text-sm font-semibold text-slate-900">
                What this list pays out
              </h4>
              <p className="text-xs text-slate-500 mt-0.5">
                Each period pays on its first day. Check this before saving — a
                missing day re-prices every row and still totals{" "}
                {conversionHours.toFixed(2)}h, so nothing else will flag it.
              </p>
            </div>
            <span className="text-xs text-slate-400 shrink-0 tabular-nums">
              {grants.totalDays} days
            </span>
          </div>

          {grants.periods.length === 0 ? (
            <p className="py-4 text-center text-sm text-slate-400">
              Nothing here, so nothing would ever be paid out.
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-xs uppercase tracking-wide text-slate-500 text-left">
                    <th className="pb-2 font-medium">Period</th>
                    <th className="pb-2 font-medium">Dates</th>
                    <th className="pb-2 font-medium text-right">Days</th>
                    <th className="pb-2 font-medium text-right">Pays</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {grants.periods.map((p) => (
                    <tr key={`${p.name}-${p.start}`}>
                      <td className="py-2 text-slate-800">{p.name}</td>
                      <td className="py-2 text-slate-500 tabular-nums">
                        {p.days === 1 ? p.start : `${p.start} – ${p.end}`}
                      </td>
                      <td className="py-2 text-right tabular-nums text-slate-500">
                        {p.days}
                      </td>
                      <td className="py-2 text-right tabular-nums font-medium">
                        {p.hours.toFixed(2)}h
                      </td>
                    </tr>
                  ))}
                </tbody>
                <tfoot>
                  <tr className="border-t-2 border-slate-200">
                    <td className="pt-2 font-medium text-slate-900" colSpan={3}>
                      Total for the year
                    </td>
                    <td className="pt-2 text-right tabular-nums font-semibold">
                      {grants.totalHours.toFixed(2)}h
                    </td>
                  </tr>
                </tfoot>
              </table>
            </div>
          )}
        </div>
      </HolidayEditor>
    </div>
  );
};

export default CalendarAdmin;
