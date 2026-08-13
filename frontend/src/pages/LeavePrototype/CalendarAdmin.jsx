import { useMemo } from "react";
import { AlertOctagon } from "lucide-react";
import { Card } from "@/components/ui/card";
import HolidayEditor from "@/pages/LeavePrototype/HolidayEditor";
import { LEVEL_POLICY, WEEKEND_LABEL } from "@/pages/LeavePrototype/mockData";

/**
 * CalendarAdmin
 *
 * The company holidays, and the figures that surround them.
 *
 * The holidays are the only part that is editable, and they are the only part
 * held in the database: they are rearranged every year, so entering them on a
 * screen beats opening a migration each December. The weekend and the level
 * entitlement are code constants shown here read-only, so an administrator can
 * see what is in force without being able to move it — changing either is a
 * pull request, which is the point.
 *
 * @param {object} props
 * @param {Array<object>} props.company
 * @param {(rows: Array<object>) => void} props.onCompanyChange
 * @returns {JSX.Element}
 */
const CalendarAdmin = ({ company, onCompanyChange }) => {
  const loadedYears = useMemo(() => {
    const years = new Set();
    for (const r of company) years.add(r.date.slice(0, 4));
    return years;
  }, [company]);

  const nextYear = String(new Date().getFullYear() + 1);
  const nextYearMissing = !loadedYears.has(nextYear);

  return (
    <div className="space-y-4">
      <Card className="p-4 space-y-3">
        <div className="flex flex-wrap items-start gap-8">
          <div className="space-y-1">
            <p className="text-xs text-slate-500">Weekend</p>
            <p className="text-sm text-slate-700">{WEEKEND_LABEL}</p>
          </div>
          <div className="space-y-1">
            <p className="text-xs text-slate-500">Yearly entitlement</p>
            <p className="text-sm text-slate-700 tabular-nums">
              {Object.entries(LEVEL_POLICY)
                .map(([level, hours]) => `${level} ${hours}h`)
                .join(" · ")}
            </p>
          </div>
        </div>
        <p className="text-xs text-slate-400">
          Read-only. These live in code rather than in this screen, so changing
          one leaves a reviewed trail instead of happening in an afternoon.
        </p>
      </Card>

      {nextYearMissing && (
        <Card className="p-4 border-l-4 border-l-rose-500">
          <div className="flex items-start gap-2.5">
            <AlertOctagon size={16} className="mt-0.5 shrink-0 text-rose-500" />
            <div>
              <h3 className="text-sm font-semibold text-slate-900">
                No {nextYear} calendar yet
              </h3>
              <p className="text-xs text-slate-500 mt-0.5">
                Every request dated in {nextYear} will be refused until there
                is.
              </p>
            </div>
          </div>
        </Card>
      )}

      <HolidayEditor
        title="Company holidays"
        blurb="Office closed. Never deducted from anyone's leave. Mark the breaks that may be worked in trade."
        rows={company}
        withExchangeable
        onChange={onCompanyChange}
      />
    </div>
  );
};

export default CalendarAdmin;
