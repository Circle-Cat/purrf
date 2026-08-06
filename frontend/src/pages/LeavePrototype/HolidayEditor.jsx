import { useMemo, useState } from "react";
import { Plus, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { datesBetween, groupHolidays } from "@/pages/LeavePrototype/leaveCalc";

/**
 * HolidayEditor
 *
 * Enter a holiday the way it is announced — a name and the dates it runs from
 * and to — and store it the way everything downstream needs it, one row per
 * date.
 *
 * Those two are not the same shape and the difference is deliberate. Whether a
 * day may be worked in trade is decided per day, not per break, and periods
 * are derived by looking for consecutive dates. A break interrupted by a
 * working day is two entries sharing a name, which a start/end column could
 * not express without a second row anyway.
 *
 * So: enter ranges, edit days.
 *
 * @param {object} props
 * @param {string} props.title
 * @param {string} props.blurb
 * @param {Array<{date: string, name: string, exchangeable?: boolean}>} props.rows
 * @param {boolean} props.withExchangeable - show per-day exchange toggles
 * @param {(rows: Array<object>) => void} props.onChange
 * @returns {JSX.Element}
 */
const HolidayEditor = ({ title, blurb, rows, withExchangeable, onChange }) => {
  const [name, setName] = useState("");
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");

  const segments = useMemo(() => groupHolidays(rows), [rows]);

  /** An empty end date means a one-day holiday. */
  const effectiveEnd = end || start;

  const taken = useMemo(() => new Set(rows.map((r) => r.date)), [rows]);

  const wouldAdd =
    start && effectiveEnd >= start ? datesBetween(start, effectiveEnd) : [];
  const collisions = wouldAdd.filter((d) => taken.has(d));

  const canAdd =
    Boolean(name.trim()) && wouldAdd.length > 0 && collisions.length === 0;

  const add = () => {
    if (!canAdd) return;
    const added = wouldAdd.map((date) => ({
      date,
      name: name.trim(),
      exchangeable: false,
    }));
    onChange([...rows, ...added].sort((a, b) => a.date.localeCompare(b.date)));
    setName("");
    setStart("");
    setEnd("");
  };

  /** Drop a whole period at once — it was entered as one. */
  const removeSegment = (segment) => {
    const drop = new Set(segment.dates);
    onChange(rows.filter((r) => !drop.has(r.date)));
  };

  const toggleDay = (date) =>
    onChange(
      rows.map((r) =>
        r.date === date ? { ...r, exchangeable: !r.exchangeable } : r,
      ),
    );

  /** Flip every day of a period in one go, to whatever it is mostly not. */
  const toggleSegment = (segment) => {
    const makeExchangeable = segment.exchangeableDays < segment.days;
    const inSegment = new Set(segment.dates);
    onChange(
      rows.map((r) =>
        inSegment.has(r.date) ? { ...r, exchangeable: makeExchangeable } : r,
      ),
    );
  };

  const slug = title.toLowerCase().replace(/\s+/g, "-");

  return (
    <Card className="p-5 space-y-4">
      <div>
        <h3 className="text-sm font-semibold text-slate-900">{title}</h3>
        <p className="text-xs text-slate-500 mt-0.5">{blurb}</p>
      </div>

      {/* Entry */}
      <div className="space-y-2">
        <div className="grid grid-cols-[1fr_auto_auto] gap-2 items-end">
          <div className="space-y-1.5 min-w-0">
            <Label htmlFor={`${slug}-name`} className="text-xs">
              Name
            </Label>
            <Input
              id={`${slug}-name`}
              value={name}
              placeholder="Spring Festival"
              onChange={(e) => setName(e.target.value)}
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor={`${slug}-start`} className="text-xs">
              From
            </Label>
            <Input
              id={`${slug}-start`}
              type="date"
              value={start}
              className="w-36"
              onChange={(e) => setStart(e.target.value)}
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor={`${slug}-end`} className="text-xs">
              To
            </Label>
            <Input
              id={`${slug}-end`}
              type="date"
              value={end}
              min={start || undefined}
              className="w-36"
              onChange={(e) => setEnd(e.target.value)}
            />
          </div>
        </div>

        <div className="flex items-center justify-between gap-3">
          <p className="text-xs text-slate-400">
            {wouldAdd.length > 0 && collisions.length === 0
              ? `Adds ${wouldAdd.length} ${wouldAdd.length === 1 ? "day" : "days"}.`
              : "Leave “To” empty for a single day."}
          </p>
          <Button size="sm" onClick={add} disabled={!canAdd}>
            <Plus size={15} />
            Add
          </Button>
        </div>

        {collisions.length > 0 && (
          <p className="text-xs text-rose-600">
            Already in the calendar: {collisions.slice(0, 4).join(", ")}
            {collisions.length > 4 && ` and ${collisions.length - 4} more`}.
          </p>
        )}
      </div>

      {/* Periods */}
      <div className="max-h-80 overflow-y-auto -mx-1 px-1">
        {segments.length === 0 ? (
          <p className="py-6 text-center text-sm text-slate-400">
            Nothing entered yet.
          </p>
        ) : (
          <ul className="divide-y divide-slate-100">
            {segments.map((s) => (
              <li key={`${s.name}-${s.start}`} className="py-2.5">
                <div className="flex items-center justify-between gap-3">
                  <div className="min-w-0">
                    <span className="text-sm text-slate-800">{s.name}</span>
                    <span className="text-xs text-slate-500 ml-2 tabular-nums">
                      {s.days === 1 ? s.start : `${s.start} – ${s.end}`}
                    </span>
                    <span className="text-xs text-slate-400 ml-2">
                      {s.days} {s.days === 1 ? "day" : "days"}
                    </span>
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="shrink-0 text-slate-400 hover:text-rose-600"
                    onClick={() => removeSegment(s)}
                    aria-label={`Remove ${s.name} ${s.start}`}
                  >
                    <Trash2 size={14} />
                  </Button>
                </div>

                {withExchangeable && (
                  <div className="flex items-center gap-1.5 mt-1.5 flex-wrap">
                    <button
                      type="button"
                      onClick={() => toggleSegment(s)}
                      className="text-xs text-slate-400 hover:text-slate-700 transition-colors mr-1"
                    >
                      {s.exchangeableDays < s.days ? "All" : "None"}
                    </button>
                    {s.dates.map((date) => {
                      const on = rows.find(
                        (r) => r.date === date,
                      )?.exchangeable;
                      return (
                        <button
                          key={date}
                          type="button"
                          onClick={() => toggleDay(date)}
                          aria-pressed={Boolean(on)}
                          title={`${date} — ${on ? "exchangeable" : "not exchangeable"}`}
                          className={`text-xs tabular-nums rounded px-1.5 py-0.5 border transition-colors ${
                            on
                              ? "bg-emerald-50 border-emerald-300 text-emerald-800"
                              : "bg-slate-50 border-slate-200 text-slate-400 hover:border-slate-300"
                          }`}
                        >
                          {date.slice(5)}
                        </button>
                      );
                    })}
                    <span className="text-xs text-slate-400 ml-1">
                      {s.exchangeableDays > 0
                        ? `${s.exchangeableDays} exchangeable`
                        : "none exchangeable"}
                    </span>
                  </div>
                )}
              </li>
            ))}
          </ul>
        )}
      </div>

      <p className="text-xs text-slate-400 pt-1 border-t border-slate-100">
        {segments.length} {segments.length === 1 ? "period" : "periods"} ·{" "}
        {rows.length} {rows.length === 1 ? "day" : "days"} stored
      </p>
    </Card>
  );
};

export default HolidayEditor;
