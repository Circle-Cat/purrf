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
 * The leave feature's whole presence on the personal dashboard, for two kinds
 * of people who overlap: those the leave system covers, and those somebody has
 * filed leave against.
 *
 * Covered people get three figures answering "what can I spend" and the things
 * they come here to do. An approver gets one more button, the way into the
 * requests waiting on them. A manager outside the leave population still
 * decides their reports' requests, so they get the card too, but only that
 * button and the holiday list: 0.00h under Available would read as "my leave is
 * zero", and anything they filed would be refused.
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
 *   isCovered: boolean,
 *   isApprover: boolean,
 *   approvalsPendingCount: number,
 *   availableHours: string|null,
 *   pendingHours: string|null,
 *   usedHours: string|null,
 * }} props
 */
const TimeOffCard = ({
  isCovered,
  isApprover,
  approvalsPendingCount,
  availableHours,
  pendingHours,
  usedHours,
}) => {
  const navigate = useNavigate();
  // Somebody outside the population has no requests to list, by definition.
  const { isSaving, saveError, file } = useMyLeaveRequests({
    enabled: isCovered,
  });
  const [isFiling, setIsFiling] = useState(false);
  const [isViewingHolidays, setIsViewingHolidays] = useState(false);

  if (!isCovered && !isApprover) return null;

  const asDays = (hours) => `${(Number(hours) / 8).toFixed(1)} days`;

  const approvals = isApprover && (
    <Button
      variant="outline"
      onClick={() => navigate(ROUTE_PATHS.LEAVE_APPROVALS)}
    >
      {approvalsPendingCount > 0
        ? `Approvals (${approvalsPendingCount})`
        : "Approvals"}
    </Button>
  );
  const holidays = (
    <Button variant="outline" onClick={() => setIsViewingHolidays(true)}>
      Company holidays
    </Button>
  );

  return (
    <Card className="border-gray-200 shadow-sm">
      <CardHeader>
        <CardTitle className="text-lg font-semibold">Time off</CardTitle>
      </CardHeader>
      <CardContent className="space-y-5">
        {isCovered ? (
          <>
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
              <Button onClick={() => setIsFiling(true)}>
                Request time off
              </Button>
              {holidays}
              <Button
                variant="outline"
                onClick={() => navigate(ROUTE_PATHS.LEAVE_REQUESTS)}
              >
                My requests
              </Button>
              {approvals}
            </div>
          </>
        ) : (
          <>
            <p className="m-0 text-sm text-muted-foreground">
              Leave isn&apos;t tracked for your account.
            </p>
            <div className="flex flex-wrap gap-2">
              {approvals}
              {holidays}
            </div>
          </>
        )}
      </CardContent>

      {isCovered && (
        <FileLeaveDialog
          isOpen={isFiling}
          isSaving={isSaving}
          saveError={saveError}
          onClose={() => setIsFiling(false)}
          onSubmit={file}
        />
      )}
      <CompanyHolidaysDialog
        isOpen={isViewingHolidays}
        onClose={() => setIsViewingHolidays(false)}
      />
    </Card>
  );
};

export default TimeOffCard;
