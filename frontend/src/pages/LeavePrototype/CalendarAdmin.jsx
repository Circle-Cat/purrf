import { useMemo, useState } from "react";
import { AlertTriangle, Plus, Trash2 } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { groupHolidays, segmentGrants } from "@/pages/LeavePrototype/leaveCalc";

/**
 * An editable list of dated rows.
 *
 * @param {object} props
 * @param {string} props.title
 * @param {string} props.blurb
 * @param {Array<object>} props.rows
 * @param {boolean} props.withExchangeable
 * @param {(rows: Array<object>) => void} props.onChange
 * @returns {JSX.Element}
 */
const DateList = ({ title, blurb, rows, withExchangeable, onChange }) => {
  const [date, setDate] = useState("");
  const [name, setName] = useState("");

  const add = () => {
    if (!date || !name.trim()) return;
    if (rows.some((r) => r.date === date)) return;
    onChange(
      [...rows, { date, name: name.trim(), exchangeable: false }].sort((a, b) =>
        a.date.localeCompare(b.date),
      ),
    );
    setDate("");
    setName("");
  };

  const remove = (target) => onChange(rows.filter((r) => r.date !== target));

  const toggle = (target) =>
    onChange(
      rows.map((r) =>
        r.date === target ? { ...r, exchangeable: !r.exchangeable } : r,
      ),
    );

  const duplicate = date && rows.some((r) => r.date === date);

  return (
    <Card className="p-5 space-y-3">
      <div>
        <h3 className="text-sm font-semibold text-slate-900">{title}</h3>
        <p className="text-xs text-slate-500 mt-0.5">{blurb}</p>
      </div>

      <div className="flex items-end gap-2">
        <div className="space-y-1.5">
          <Label htmlFor={`${title}-date`} className="text-xs">
            Date
          </Label>
          <Input
            id={`${title}-date`}
            type="date"
            value={date}
            className="w-40"
            onChange={(e) => setDate(e.target.value)}
          />
        </div>
        <div className="space-y-1.5 flex-1 min-w-0">
          <Label htmlFor={`${title}-name`} className="text-xs">
            Name
          </Label>
          <Input
            id={`${title}-name`}
            value={name}
            placeholder="Spring Festival"
            onChange={(e) => setName(e.target.value)}
          />
        </div>
        <Button size="sm" onClick={add} disabled={!date || !name.trim()}>
          <Plus size={15} />
          Add
        </Button>
      </div>

      {duplicate && (
        <p className="text-xs text-rose-600">{date} is already in this list.</p>
      )}

      <div className="max-h-64 overflow-y-auto -mx-1 px-1">
        <ul className="divide-y divide-slate-100">
          {rows.map((r) => (
            <li
              key={r.date}
              className="py-1.5 flex items-center justify-between gap-3 text-sm"
            >
              <span className="tabular-nums text-slate-500 w-24 shrink-0">
                {r.date}
              </span>
              <span className="flex-1 min-w-0 truncate text-slate-700">
                {r.name}
              </span>
              {withExchangeable && (
                <label className="flex items-center gap-1.5 text-xs text-slate-500 shrink-0 cursor-pointer">
                  <Checkbox
                    checked={r.exchangeable}
                    onCheckedChange={() => toggle(r.date)}
                  />
                  Exchangeable
                </label>
              )}
              <Button
                variant="ghost"
                size="sm"
                className="shrink-0 text-slate-400 hover:text-rose-600"
                onClick={() => remove(r.date)}
                aria-label={`Remove ${r.date}`}
              >
                <Trash2 size={14} />
              </Button>
            </li>
          ))}
        </ul>
      </div>

      <p className="text-xs text-slate-400 pt-1 border-t border-slate-100">
        {rows.length} {rows.length === 1 ? "day" : "days"}
      </p>
    </Card>
  );
};

/**
 * CalendarAdmin
 *
 * The once-a-year job: type in next year's two calendars.
 *
 * The payout panel below the two lists is the point of the screen. Statutory
 * days are the
 * denominator of every conversion payout, so leaving one out does not fail —
 * it silently re-prices every period of the year and the annual total still
 * comes to the right number. Showing the derived periods back, with what each
 * one pays and when, is the only place that mistake can be caught.
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
  const companySegments = useMemo(() => groupHolidays(company), [company]);

  return (
    <div className="space-y-4">
      <p className="text-sm text-slate-500">
        Entered by hand once a year, from the published government calendar.
        Nothing is fetched — a yearly one-off is not worth an external feed that
        can drift, and next year&apos;s dates are only announced in November
        anyway.
      </p>

      <div className="grid lg:grid-cols-2 gap-4">
        <DateList
          title="Company holidays"
          blurb="The office is closed. Never deducted from anyone's leave. Mark the days that may be worked in trade."
          rows={company}
          withExchangeable
          onChange={onCompanyChange}
        />
        <DateList
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
                a payout that moved. Delete a day above and watch every row
                change.
              </p>
            </div>
          </>
        )}
      </Card>

      <Card className="p-5">
        <h3 className="text-sm font-semibold text-slate-900 mb-1">
          Company holiday periods
        </h3>
        <p className="text-xs text-slate-500 mb-3">
          Shown back the way employees will see them, so a mistyped date is
          visible as a break that split or ran long.
        </p>
        <ul className="divide-y divide-slate-100">
          {companySegments.map((s) => (
            <li
              key={`${s.name}-${s.start}`}
              className="py-2 flex items-center justify-between gap-4 text-sm"
            >
              <span className="text-slate-700">
                <span className="tabular-nums text-slate-500 mr-3">
                  {s.days === 1 ? s.start : `${s.start} – ${s.end}`}
                </span>
                {s.name}
              </span>
              <span className="text-xs text-slate-400 shrink-0">
                {s.days} {s.days === 1 ? "day" : "days"}
                {s.exchangeableDays > 0 &&
                  ` · ${s.exchangeableDays} exchangeable`}
              </span>
            </li>
          ))}
        </ul>
      </Card>
    </div>
  );
};

export default CalendarAdmin;
