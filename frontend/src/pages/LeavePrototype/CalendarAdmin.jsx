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

/**
 * CalendarAdmin
 *
 * One region's company holidays and the figures that go with them.
 *
 * There is no statutory calendar here. It used to exist only to decide when
 * extra paid leave was paid out; now half of that accrues weekly and the other
 * half is granted by hand before each holiday, so nothing reads a government
 * calendar and there is nothing to keep in step with one.
 *
 * Editable rather than loaded by migration because a region is created the day
 * somebody is hired into it, and its holidays and figures have to exist from
 * that moment.
 *
 * @param {object} props
 * @param {string} props.region
 * @param {(region: string) => void} props.onRegionChange
 * @param {object} props.settings - {weeklyExtraHours, holidayGrantAllowance, weekendLabel}
 * @param {(settings: object) => void} props.onSettingsChange
 * @param {Array<object>} props.company
 * @param {(rows: Array<object>) => void} props.onCompanyChange
 * @returns {JSX.Element}
 */
const CalendarAdmin = ({
  region,
  onRegionChange,
  settings,
  onSettingsChange,
  company,
  onCompanyChange,
}) => {
  const loadedYears = useMemo(() => {
    const years = new Set();
    for (const r of company) years.add(r.date.slice(0, 4));
    return years;
  }, [company]);

  const nextYear = String(new Date().getFullYear() + 1);
  const nextYearMissing = !loadedYears.has(nextYear);

  const set = (key, value) => onSettingsChange({ ...settings, [key]: value });

  return (
    <div className="space-y-4">
      <Card className="p-4 space-y-3">
        <div className="flex flex-wrap items-end gap-4">
          <div className="space-y-1.5">
            <Label htmlFor="calendar-region" className="text-xs">
              Region
            </Label>
            <Select value={region} onValueChange={onRegionChange}>
              <SelectTrigger id="calendar-region" className="w-44">
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
            <Label htmlFor="calendar-weekly" className="text-xs">
              Extra leave, accrued weekly
            </Label>
            <Input
              id="calendar-weekly"
              type="number"
              step="8"
              className="w-36"
              value={settings.weeklyExtraHours}
              onChange={(e) => set("weeklyExtraHours", Number(e.target.value))}
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="calendar-grant" className="text-xs">
              Extra leave, granted by hand
            </Label>
            <Input
              id="calendar-grant"
              type="number"
              step="8"
              className="w-36"
              value={settings.holidayGrantAllowance}
              onChange={(e) =>
                set("holidayGrantAllowance", Number(e.target.value))
              }
            />
          </div>
          <div className="space-y-1.5 min-w-36">
            <Label className="text-xs">Weekend</Label>
            <p className="text-sm text-slate-700 h-9 flex items-center">
              {settings.weekendLabel}
            </p>
          </div>
        </div>
        <p className="text-xs text-slate-400">
          Regional. The level entitlement is global and lives in code; these do
          not, because a new region needs them the day it is created. Set the
          granted figure to zero for a region that does not do it — the grant
          screen then has nothing to issue there.
        </p>
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
                is.
              </p>
            </div>
          </div>
        </Card>
      )}

      <HolidayEditor
        title="Company holidays"
        blurb="Office closed. Never deducted from anyone's leave. Mark the days that may be worked in trade."
        rows={company}
        withExchangeable
        onChange={onCompanyChange}
      />
    </div>
  );
};

export default CalendarAdmin;
