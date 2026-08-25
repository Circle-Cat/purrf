import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ROUTE_PATHS } from "@/constants/RoutePaths";
import CompanyHolidaysDialog from "@/pages/Leave/components/CompanyHolidaysDialog";
import FileLeaveDialog from "@/pages/Leave/components/FileLeaveDialog";
import { useMyLeaveRequests } from "@/pages/Leave/hooks/useMyLeaveRequests";

/**
 * One figure in the card.
 *
 * Rendered exactly as the server sent it. The days underneath are the one
 * derived number here, and it is presentation: eight hours is a day by policy,
 * and nothing downstream reads it.
 *
 * @param {{label: string, hours: string, hint: string, isRed?: boolean}} props
 */
const Stat = ({ label, hours, hint, isRed = false }) => (
  <div className="min-w-0">
    <p className="m-0 text-xs uppercase tracking-wide text-muted-foreground">
      {label}
    </p>
    <p
      className={`m-0 mt-1 text-2xl font-semibold tabular-nums ${
        isRed ? "text-rose-600" : ""
      }`}
    >
      {`${hours}h`}
    </p>
    <p className="m-0 mt-0.5 text-xs text-muted-foreground">{hint}</p>
  </div>
);

/**
 * TimeOffCard
 *
 * The leave feature's whole presence on the personal dashboard: three figures
 * answering "what can I spend", and the things anyone comes here to do.
 *
 * The card never grows. Requesting and the holiday list open in dialogs, and
 * the history is a page of its own, because a dashboard card that expands into
 * a long list stops being a dashboard card.
 *
 * Available is the balance less the hours undecided requests already hold, so
 * it cannot say somebody can afford leave that filing would then flag. All
 * three figures come from the server; the only arithmetic here is hours into
 * days for the hint.
 *
 * @param {{
 *   availableHours: string|null,
 *   pendingHours: string|null,
 *   usedHours: string|null,
 * }} props
 */
const TimeOffCard = ({ availableHours, pendingHours, usedHours }) => {
  const navigate = useNavigate();
  const { requests, isSaving, saveError, file } = useMyLeaveRequests();
  const [isFiling, setIsFiling] = useState(false);
  const [isViewingHolidays, setIsViewingHolidays] = useState(false);

  const pendingCount = requests.filter(
    (row) => row.status === "pending",
  ).length;
  const asDays = (hours) => `${(Number(hours) / 8).toFixed(1)} days`;

  return (
    <Card className="border-gray-200 shadow-sm">
      <CardHeader className="flex flex-row items-start justify-between gap-4">
        <CardTitle className="text-lg font-semibold">Time off</CardTitle>
        {pendingCount > 0 && (
          <span className="rounded-full border border-amber-200 bg-amber-50 px-2 py-0.5 text-xs text-amber-700">
            {`${pendingCount} awaiting a decision`}
          </span>
        )}
      </CardHeader>
      <CardContent className="space-y-5">
        <div className="grid grid-cols-3 gap-6">
          <Stat
            label="Available"
            hours={availableHours ?? "0.00"}
            hint={asDays(availableHours ?? 0)}
            isRed={Number(availableHours) < 0}
          />
          <Stat
            label="Pending"
            hours={pendingHours ?? "0.00"}
            hint="Requested, not yet decided"
          />
          <Stat
            label="Used"
            hours={usedHours ?? "0.00"}
            hint="Approved and taken this year"
          />
        </div>

        <div className="flex flex-wrap gap-2">
          <Button onClick={() => setIsFiling(true)}>Request time off</Button>
          <Button variant="outline" onClick={() => setIsViewingHolidays(true)}>
            Company holidays
          </Button>
          <Button
            variant="outline"
            onClick={() => navigate(ROUTE_PATHS.LEAVE_REQUESTS)}
          >
            My requests
          </Button>
        </div>
      </CardContent>

      <FileLeaveDialog
        isOpen={isFiling}
        isSaving={isSaving}
        saveError={saveError}
        onClose={() => setIsFiling(false)}
        onSubmit={file}
      />
      <CompanyHolidaysDialog
        isOpen={isViewingHolidays}
        onClose={() => setIsViewingHolidays(false)}
      />
    </Card>
  );
};

export default TimeOffCard;
