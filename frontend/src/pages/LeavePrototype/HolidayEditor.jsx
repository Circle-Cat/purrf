import { useMemo, useState } from "react";
import { Plus, Trash2 } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { datesBetween, groupHolidays } from "@/pages/LeavePrototype/leaveCalc";

/**
 * HolidayEditor
 *
 * Enter a holiday as it is announced — a name and the dates it runs — and
 * store it as one row per date, which is what everything downstream needs:
 * exchangeability is decided per day, and periods are found by looking for
 * consecutive dates.
 *
 * A break that is only partly tradeable is entered as two rows with the same
 * name. They merge back into one period on display, so nothing is lost and
 * there is no per-day control to fiddle with.
 *
 * @param {object} props
 * @param {string} props.title
 * @param {string} props.blurb - one line, shown under the title
 * @param {Array<{date: string, name: string, exchangeable?: boolean}>} props.rows
 * @param {boolean} props.withExchangeable
 * @param {(rows: Array<object>) => void} props.onChange
 * @param {(segment: object) => string|null} [props.annotate] - extra figure to
 *   show on each period row, for anything this list derives
 * @param {string} [props.footnote] - shown next to the period/day count
 * @returns {JSX.Element}
 */
const HolidayEditor = ({
  title,
  blurb,
  rows,
  withExchangeable,
  onChange,
  annotate,
  footnote,
}) => {
  const [name, setName] = useState("");
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [exchangeable, setExchangeable] = useState(false);

  const segments = useMemo(() => groupHolidays(rows), [rows]);
  const taken = useMemo(() => new Set(rows.map((r) => r.date)), [rows]);

  /** An empty end date means a one-day holiday. */
  const effectiveEnd = end || start;
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
      exchangeable,
    }));
    onChange([...rows, ...added].sort((a, b) => a.date.localeCompare(b.date)));
    setName("");
    setStart("");
    setEnd("");
    setExchangeable(false);
  };

  const removeSegment = (segment) => {
    const drop = new Set(segment.dates);
    onChange(rows.filter((r) => !drop.has(r.date)));
  };

  const slug = title.toLowerCase().replace(/\s+/g, "-");

  return (
    <Card className="p-5 space-y-4">
      <div>
        <h3 className="text-sm font-semibold text-slate-900">{title}</h3>
        <p className="text-xs text-slate-500 mt-0.5">{blurb}</p>
      </div>

      <div className="flex flex-wrap items-end gap-2">
        <div className="space-y-1.5 flex-1 min-w-36">
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
        {withExchangeable && (
          <label className="flex items-center gap-2 text-sm text-slate-600 h-9 px-1 cursor-pointer">
            <Checkbox
              checked={exchangeable}
              onCheckedChange={(v) => setExchangeable(Boolean(v))}
            />
            Exchangeable
          </label>
        )}
        <Button size="sm" onClick={add} disabled={!canAdd} className="h-9">
          <Plus size={15} />
          Add
        </Button>
      </div>

      {collisions.length > 0 ? (
        <p className="text-xs text-rose-600">
          Already in the calendar: {collisions.slice(0, 4).join(", ")}
          {collisions.length > 4 && ` and ${collisions.length - 4} more`}.
        </p>
      ) : (
        <p className="text-xs text-slate-400">
          Leave “To” empty for a single day.
          {withExchangeable &&
            " For a break that is only partly tradeable, add it as two entries with the same name."}
        </p>
      )}

      <div className="max-h-72 overflow-y-auto -mx-1 px-1">
        {segments.length === 0 ? (
          <p className="py-6 text-center text-sm text-slate-400">
            Nothing entered yet.
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
                  {withExchangeable && s.exchangeableDays > 0 && (
                    <Badge variant="outline" className="text-xs">
                      {s.exchangeableDays === s.days
                        ? "Exchangeable"
                        : `${s.exchangeableDays}/${s.days}`}
                    </Badge>
                  )}
                  <Button
                    variant="ghost"
                    size="sm"
                    className="text-slate-400 hover:text-rose-600"
                    onClick={() => removeSegment(s)}
                    aria-label={`Remove ${s.name} ${s.start}`}
                  >
                    <Trash2 size={14} />
                  </Button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="flex items-baseline justify-between gap-3 pt-1 border-t border-slate-100 text-xs text-slate-400">
        <span className="tabular-nums">
          {segments.length} periods · {rows.length} days
        </span>
        {footnote && <span className="tabular-nums">{footnote}</span>}
      </div>
    </Card>
  );
};

export default HolidayEditor;
