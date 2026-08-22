import { useState } from "react";
import { Navigate } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ROUTE_PATHS } from "@/constants/RoutePaths";
import CompanyHolidaysDialog from "@/pages/Leave/RequestsPage/components/CompanyHolidaysDialog";
import FileLeaveDialog from "@/pages/Leave/RequestsPage/components/FileLeaveDialog";
import MyRequestRow from "@/pages/Leave/RequestsPage/components/MyRequestRow";
import { useLeaveCoverage } from "@/pages/Leave/hooks/useLeaveCoverage";
import { useLeaveEnabled } from "@/pages/Leave/hooks/useLeaveEnabled";
import {
  isWithdrawable,
  useMyLeaveRequests,
} from "@/pages/Leave/hooks/useMyLeaveRequests";
import { LEAVE_CALENDAR_ZONE_LABEL } from "@/pages/Leave/utils/leaveDates";

/**
 * LeaveRequestsPage
 *
 * The signed-in employee's own leave: what they have asked for, and the two
 * ways in to asking for more.
 *
 * Behind the leave feature flag, and the address is covered as well as the
 * entry point. Somebody the feature does not apply to is sent away rather than
 * shown an empty list: an empty list reads as "you have never taken leave",
 * which is a different statement from "leave is not tracked for you".
 *
 * @returns {JSX.Element}
 */
const LeaveRequestsPage = () => {
  const isEnabled = useLeaveEnabled();
  const { isCovered, isLoading: isCoverageLoading } = useLeaveCoverage({
    enabled: isEnabled,
  });
  const {
    requests,
    isLoading,
    loadError,
    isSaving,
    saveError,
    withdrawingId,
    load,
    file,
    withdraw,
  } = useMyLeaveRequests({ enabled: isEnabled });

  const [isFiling, setIsFiling] = useState(false);
  const [isViewingHolidays, setIsViewingHolidays] = useState(false);

  if (!isEnabled) {
    return <Navigate to={ROUTE_PATHS.PERSONAL_DASHBOARD} replace />;
  }

  // Waiting rather than deciding: coverage fails closed, so acting on it while
  // it is still false-because-loading would bounce somebody who is covered.
  if (isCoverageLoading) {
    return <p className="text-sm text-muted-foreground">Loading…</p>;
  }

  if (!isCovered) {
    return (
      <div className="space-y-2">
        <h2 className="m-0 text-lg font-medium">My Leave</h2>
        <p className="text-sm text-muted-foreground">
          Leave isn't tracked for your account.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <h2 className="m-0 text-lg font-medium">My Leave</h2>
        <div className="flex items-center gap-2">
          <span className="text-sm text-muted-foreground">
            {LEAVE_CALENDAR_ZONE_LABEL}
          </span>
          <Button variant="outline" onClick={() => setIsViewingHolidays(true)}>
            Company holidays
          </Button>
          <Button onClick={() => setIsFiling(true)}>Request leave</Button>
        </div>
      </div>

      {saveError && !isFiling && (
        <p className="text-sm text-red-700">{saveError}</p>
      )}

      <Card className="border-gray-200 shadow-sm">
        <CardHeader>
          <CardTitle className="text-lg font-semibold">My requests</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading && (
            <p className="text-sm text-muted-foreground">Loading…</p>
          )}

          {!isLoading && loadError && (
            <div className="flex flex-col items-start gap-3">
              <p className="text-sm text-muted-foreground">
                Couldn't load your requests.
              </p>
              <Button onClick={load}>Retry</Button>
            </div>
          )}

          {!isLoading && !loadError && requests.length === 0 && (
            <p className="text-sm text-muted-foreground">
              You haven't asked for any leave yet.
            </p>
          )}

          {!isLoading && !loadError && requests.length > 0 && (
            <ul className="divide-y divide-gray-100">
              {requests.map((row) => (
                <MyRequestRow
                  key={row.requestId}
                  row={row}
                  isWithdrawable={isWithdrawable(row)}
                  isWithdrawing={withdrawingId !== null}
                  onWithdraw={withdraw}
                />
              ))}
            </ul>
          )}
        </CardContent>
      </Card>

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
    </div>
  );
};

export default LeaveRequestsPage;
