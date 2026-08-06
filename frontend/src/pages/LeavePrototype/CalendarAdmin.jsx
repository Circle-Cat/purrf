import { useMemo } from "react";
import { AlertTriangle } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import HolidayEditor from "@/pages/LeavePrototype/HolidayEditor";
import { segmentGrants } from "@/pages/LeavePrototype/leaveCalc";

/**
 * CalendarAdmin
 *
 * The once-a-year job: type in next year's two calendars.
 *
 * The payout panel below the two editors is the point of the screen. Statutory
 * days are the denominator of every conversion payout, so leaving one out does
 * not fail — it silently re-prices every period of the year while the annual
 * total still comes to exactly the right number. Showing the derived periods
 * back, with what each pays and when, is the only place that mistake is
 * visible.
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
      <p className="text-sm text-slate-500">
        Entered by hand once a year, from the published government calendar.
        Nothing is fetched — a yearly one-off is not worth an external feed that
        can drift, and next year&apos;s dates are only announced in November
        anyway.
      </p>

      <div className="grid lg:grid-cols-2 gap-4">
        <HolidayEditor
          title="Company holidays"
          blurb="The office is closed. Never deducted from anyone's leave. Mark the days that may be worked in trade."
          rows={company}
          withExchangeable
          onChange={onCompanyChange}
        />
        <HolidayEditor
          title="Statutory holidays"
          blurb="Drives when conversion hours are paid out. Has no effect on whether a leave day is deducted."
          rows={statutory}
          withExchangeable={false}
          onChange={onStatutoryChange}
        />
      </div>

      {/* The check that has to be read before saving */}
      <Card className="p-5">
        <div className="flex items-start justify-between gap-4 mb-3">
          <div>
            <h3 className="text-sm font-semibold text-slate-900">
              What this calendar pays out
            </h3>
            <p className="text-xs text-slate-500 mt-0.5">
              Derived from the statutory list — periods are consecutive dates
              sharing a name. Read this before saving.
            </p>
          </div>
          <Badge variant="outline" className="shrink-0">
            {grants.periods.length}{" "}
            {grants.periods.length === 1 ? "period" : "periods"} ·{" "}
            {grants.totalDays} days
          </Badge>
        </div>

        {grants.periods.length === 0 ? (
          <p className="py-6 text-center text-sm text-slate-400">
            No statutory days entered, so nothing would ever be paid out.
          </p>
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-xs uppercase tracking-wide text-slate-500 text-left">
                    <th className="pb-2 font-medium">Period</th>
                    <th className="pb-2 font-medium">Dates</th>
                    <th className="pb-2 font-medium text-right">Days</th>
                    <th className="pb-2 font-medium text-right">Pays</th>
                    <th className="pb-2 font-medium text-right">Lands on</th>
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
                      <td className="py-2 text-right tabular-nums text-slate-500">
                        {p.start}
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
                    <td />
                  </tr>
                </tfoot>
              </table>
            </div>

            <div className="flex items-start gap-2 mt-4 pt-3 border-t border-slate-100 text-xs text-slate-500">
              <AlertTriangle size={14} className="mt-0.5 shrink-0" />
              <p>
                The total always comes to {conversionHours.toFixed(2)}h,
                whatever you type — it is divided out of the entitlement, not
                added up from the days. So a missing day will not show up as a
                wrong total. It shows up here, as a period that split in two or
                a payout that moved. Delete a period above and watch every row
                change.
              </p>
            </div>
          </>
        )}
      </Card>
    </div>
  );
};

export default CalendarAdmin;
