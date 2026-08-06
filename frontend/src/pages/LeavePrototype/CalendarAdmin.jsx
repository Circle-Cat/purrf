import { useMemo } from "react";
import { AlertOctagon } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import HolidayEditor from "@/pages/LeavePrototype/HolidayEditor";
import { REGIONS } from "@/pages/LeavePrototype/mockData";
import { segmentGrants } from "@/pages/LeavePrototype/leaveCalc";

/**
 * CalendarAdmin
 *
 * Both calendars for one region, and the regional figures they are paid out
 * against.
 *
 * This is editable rather than loaded by migration because a region is created
 * the day somebody is hired into it. Its holidays, its conversion entitlement
 * and which days it treats as the weekend all have to exist from that moment,
 * and none of those dates can be planned around a yearly release.
 *
 * The payout figures beside each statutory period are the only check on that
 * list. Its days are the denominator of every payout, so a missing one
 * re-prices each period while the annual total still comes to exactly the
 * entitlement — the year is divided out of it, not summed from the days.
 *
 * @param {object} props
 * @param {string} props.region
 * @param {(region: string) => void} props.onRegionChange
 * @param {object} props.settings - {conversionHours, weekendLabel}
 * @param {(settings: object) => void} props.onSettingsChange
 * @param {Array<object>} props.company
 * @param {Array<object>} props.statutory
 * @param {(rows: Array<object>) => void} props.onCompanyChange
 * @param {(rows: Array<object>) => void} props.onStatutoryChange
 * @returns {JSX.Element}
 */
const CalendarAdmin = ({
  region,
  onRegionChange,
  settings,
  onSettingsChange,
  company,
  statutory,
  onCompanyChange,
  onStatutoryChange,
}) => {
  const grants = useMemo(
    () => segmentGrants(statutory, settings.conversionHours),
    [statutory, settings.conversionHours],
  );

  const hoursByPeriod = useMemo(
    () => new Map(grants.periods.map((p) => [`${p.name}-${p.start}`, p.hours])),
    [grants],
  );

  const loadedYears = useMemo(() => {
    const years = new Set();
    for (const r of [...company, ...statutory]) years.add(r.date.slice(0, 4));
    return years;
  }, [company, statutory]);

  const nextYear = String(new Date().getFullYear() + 1);
  const nextYearMissing = !loadedYears.has(nextYear);

  return (
    <div className="space-y-4">
      <Card className="p-4">
        <div className="flex flex-wrap items-end gap-4">
          <div className="space-y-1.5">
            <Label htmlFor="calendar-region" className="text-xs">
              Region
            </Label>
            <Select value={region} onValueChange={onRegionChange}>
              <SelectTrigger id="calendar-region" className="w-48">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {Object.entries(REGIONS).map(([key, r]) => (
                  <SelectItem key={key} value={key}>
                    {r.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="calendar-conversion" className="text-xs">
              Conversion hours
            </Label>
            <Input
              id="calendar-conversion"
              type="number"
              step="8"
              className="w-32"
              value={settings.conversionHours}
              onChange={(e) =>
                onSettingsChange({
                  ...settings,
                  conversionHours: Number(e.target.value),
                })
              }
            />
          </div>
          <div className="space-y-1.5 min-w-40">
            <Label className="text-xs">Weekend</Label>
            <p className="text-sm text-slate-700 h-9 flex items-center">
              {settings.weekendLabel}
            </p>
          </div>
          <p className="text-xs text-slate-400 flex-1 min-w-48 pb-2">
            Regional. Level entitlement is global and lives in code; these do
            not, because a new region needs them the day it is created.
          </p>
        </div>
      </Card>

      {nextYearMissing && (
        <Card className="p-4 border-l-4 border-l-rose-500">
          <div className="flex items-start gap-2.5">
            <AlertOctagon size={16} className="mt-0.5 shrink-0 text-rose-500" />
            <div>
              <h3 className="text-sm font-semibold text-slate-900">
                No {nextYear} calendar for {REGIONS[region].label}
              </h3>
              <p className="text-xs text-slate-500 mt-0.5">
                Every request dated in {nextYear} will be refused until there
                is, and no conversion hours will be paid out that year.
              </p>
            </div>
          </div>
        </Card>
      )}

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
        Check the statutory periods against the published announcement. A
        missing day still totals {settings.conversionHours.toFixed(2)}h — the
        year is divided out of the entitlement, not added up from the days — so
        it will not show up anywhere else.
      </p>
    </div>
  );
};

export default CalendarAdmin;
