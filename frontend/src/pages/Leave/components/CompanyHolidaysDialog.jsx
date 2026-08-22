import { useCallback, useEffect, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { getLeaveHolidayYears, getLeaveHolidays } from "@/api/leaveApi";
import {
  LEAVE_CALENDAR_ZONE_LABEL,
  formatBusinessRange,
} from "@/pages/Leave/utils/leaveDates";

/**
 * CompanyHolidaysDialog
 *
 * The company holidays for one year, so somebody filing a request can see
 * which days are already off and which of them can be traded.
 *
 * The year list and which year is current both come from the server. A browser
 * in another timezone would otherwise disagree about which year it is, and on
 * 1 January that disagreement picks the wrong calendar.
 *
 * A year nobody has entered answers with an empty list rather than an error:
 * absent is a normal state for a year that has not been planned yet.
 *
 * @param {{isOpen: boolean, onClose: () => void}} props
 */
const CompanyHolidaysDialog = ({ isOpen, onClose }) => {
  const [years, setYears] = useState([]);
  const [year, setYear] = useState(null);
  const [segments, setSegments] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [loadError, setLoadError] = useState(false);

  useEffect(() => {
    if (!isOpen) return;
    setLoadError(false);
    getLeaveHolidayYears()
      .then(({ data }) => {
        // The two years the page must offer whether or not they hold rows.
        const offered = Array.from(
          new Set(
            [...(data?.years ?? []), data?.currentYear, data?.nextYear].filter(
              (value) => typeof value === "number",
            ),
          ),
        ).sort();
        setYears(offered);
        setYear((previous) => previous ?? data?.currentYear ?? null);
      })
      .catch(() => setLoadError(true));
  }, [isOpen]);

  const loadYear = useCallback((wanted) => {
    if (wanted === null || wanted === undefined) return;
    setIsLoading(true);
    setLoadError(false);
    getLeaveHolidays(wanted)
      .then(({ data }) => setSegments(data?.segments ?? []))
      .catch(() => {
        setLoadError(true);
        setSegments([]);
      })
      .finally(() => setIsLoading(false));
  }, []);

  useEffect(() => {
    if (isOpen) loadYear(year);
  }, [isOpen, year, loadYear]);

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Company holidays</DialogTitle>
        </DialogHeader>

        <div className="space-y-4">
          <div className="flex items-end justify-between gap-3">
            <div className="space-y-1.5">
              <Label htmlFor="holiday-year">Year</Label>
              <select
                id="holiday-year"
                className="h-9 rounded-md border border-input bg-transparent px-3 text-sm"
                value={year ?? ""}
                onChange={(event) => setYear(Number(event.target.value))}
              >
                {years.map((option) => (
                  <option key={option} value={option}>
                    {option}
                  </option>
                ))}
              </select>
            </div>
            <span className="text-xs text-muted-foreground">
              {LEAVE_CALENDAR_ZONE_LABEL}
            </span>
          </div>

          {isLoading && (
            <p className="text-sm text-muted-foreground">Loading…</p>
          )}

          {!isLoading && loadError && (
            <div className="flex flex-col items-start gap-3">
              <p className="text-sm text-muted-foreground">
                Couldn't load the calendar.
              </p>
              <Button onClick={() => loadYear(year)}>Retry</Button>
            </div>
          )}

          {!isLoading && !loadError && segments.length === 0 && (
            <p className="text-sm text-muted-foreground">
              No holidays have been entered for {year} yet.
            </p>
          )}

          {!isLoading && !loadError && segments.length > 0 && (
            <ul className="divide-y divide-gray-100">
              {segments.map((segment) => (
                <li
                  key={`${segment.startDate}-${segment.name}`}
                  className="flex items-start justify-between gap-3 py-2"
                >
                  <div className="min-w-0">
                    <p className="m-0 text-sm font-medium">{segment.name}</p>
                    <p className="m-0 text-sm text-muted-foreground">
                      {formatBusinessRange(segment.startDate, segment.endDate)}
                      {` · ${segment.dayCount} ${
                        segment.dayCount === 1 ? "day" : "days"
                      }`}
                    </p>
                  </div>
                  {/* Whether it can be traded is a property of the whole
                      holiday, not of single days within it. */}
                  {segment.isExchangeable && (
                    <Badge variant="secondary">Exchangeable</Badge>
                  )}
                </li>
              ))}
            </ul>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
};

export default CompanyHolidaysDialog;
