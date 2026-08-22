import { useState } from "react";
import { Navigate } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { ROUTE_PATHS } from "@/constants/RoutePaths";
import SegmentRow from "@/pages/Leave/CalendarAdminPage/components/SegmentRow";
import { useLeaveCalendarAdmin } from "@/pages/Leave/hooks/useLeaveCalendarAdmin";
import { useLeaveEnabled } from "@/pages/Leave/hooks/useLeaveEnabled";
import { LEAVE_CALENDAR_ZONE_LABEL } from "@/pages/Leave/utils/leaveDates";

/**
 * LeaveCalendarAdminPage
 *
 * Where the company holidays for a year are entered.
 *
 * This is the only way holidays ever get into the system -- there is no data
 * migration for them -- and it is the calendar every leave request is measured
 * against: a year with nothing in it refuses every request dated in it, and a
 * year missing a holiday quietly overcharges everybody who takes leave across
 * it.
 *
 * A year is saved whole. The endpoint replaces it, so a row removed here and
 * saved is deleted, and that is confirmed before it happens rather than
 * reported after.
 *
 * Nothing here validates a segment. The server refuses six ways and each
 * message names the holiday at fault; a copy of those rules in the browser
 * would be free to disagree with the one that actually refuses.
 *
 * @returns {JSX.Element}
 */
const LeaveCalendarAdminPage = () => {
  const isEnabled = useLeaveEnabled();
  const {
    years,
    year,
    setYear,
    segments,
    isLoading,
    loadError,
    isSaving,
    saveError,
    isDirty,
    load,
    edit,
    add,
    remove,
    save,
  } = useLeaveCalendarAdmin({ enabled: isEnabled });

  const [isConfirming, setIsConfirming] = useState(false);

  if (!isEnabled) {
    return <Navigate to={ROUTE_PATHS.PERSONAL_DASHBOARD} replace />;
  }

  const totalDays = segments.reduce((running, segment) => {
    if (!segment.startDate || !segment.endDate) return running;
    // Whole days between two `YYYY-MM-DD` strings, counted without building a
    // Date: Date.UTC takes the parts as numbers and never applies a zone.
    const [fromYear, fromMonth, fromDay] = segment.startDate
      .split("-")
      .map(Number);
    const [toYear, toMonth, toDay] = segment.endDate.split("-").map(Number);
    const from = Date.UTC(fromYear, fromMonth - 1, fromDay);
    const to = Date.UTC(toYear, toMonth - 1, toDay);
    if (Number.isNaN(from) || Number.isNaN(to) || to < from) return running;
    return running + (to - from) / 86400000 + 1;
  }, 0);

  const confirmAndSave = async () => {
    setIsConfirming(false);
    await save();
  };

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <h2 className="m-0 text-lg font-medium">Company holiday calendar</h2>
        <span className="text-sm text-muted-foreground">
          {LEAVE_CALENDAR_ZONE_LABEL}
        </span>
      </div>

      <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="space-y-1.5">
          <Label htmlFor="calendar-year">Year</Label>
          <select
            id="calendar-year"
            className="h-9 rounded-md border border-input bg-transparent px-3 text-sm"
            value={year ?? ""}
            disabled={isSaving}
            onChange={(event) => setYear(Number(event.target.value))}
          >
            {years.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" disabled={isSaving} onClick={add}>
            Add a holiday
          </Button>
          <Button
            disabled={isSaving || !isDirty}
            onClick={() => setIsConfirming(true)}
          >
            {isSaving ? "Saving…" : "Save the year"}
          </Button>
        </div>
      </div>

      {saveError && <p className="text-sm text-red-700">{saveError}</p>}

      <Card className="border-gray-200 shadow-sm">
        <CardHeader>
          <CardTitle className="text-lg font-semibold">
            {year
              ? `${year} — ${segments.length} holidays, ${totalDays} days`
              : "—"}
          </CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading && (
            <p className="text-sm text-muted-foreground">Loading…</p>
          )}

          {!isLoading && loadError && (
            <div className="flex flex-col items-start gap-3">
              <p className="text-sm text-muted-foreground">
                Couldn't load the calendar.
              </p>
              <Button onClick={() => load(year)}>Retry</Button>
            </div>
          )}

          {!isLoading && !loadError && segments.length === 0 && (
            <p className="text-sm text-muted-foreground">
              Nothing entered for {year} yet. A year left empty refuses every
              leave request dated in it.
            </p>
          )}

          {!isLoading && !loadError && segments.length > 0 && (
            <ul className="divide-y divide-gray-100">
              {segments.map((segment, index) => (
                <SegmentRow
                  key={index}
                  index={index}
                  segment={segment}
                  isSaving={isSaving}
                  onEdit={edit}
                  onRemove={remove}
                />
              ))}
            </ul>
          )}
        </CardContent>
      </Card>

      <Dialog
        open={isConfirming}
        onOpenChange={(open) => !open && setIsConfirming(false)}
      >
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>{`Replace all of ${year}?`}</DialogTitle>
          </DialogHeader>
          {/* Said before it happens, not reported after: saving is the whole
              year, so anything taken off this page is deleted. */}
          <p className="text-sm text-muted-foreground">
            {`Saving replaces every company holiday in ${year} with the ${segments.length} on this page, covering ${totalDays} days. Anything you removed is deleted.`}
          </p>
          <DialogFooter>
            <Button variant="outline" onClick={() => setIsConfirming(false)}>
              Cancel
            </Button>
            <Button onClick={confirmAndSave}>{`Replace ${year}`}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default LeaveCalendarAdminPage;
