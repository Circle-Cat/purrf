import { Navigate } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ROUTE_PATHS } from "@/constants/RoutePaths";
import MyRequestRow from "@/pages/Leave/RequestsPage/components/MyRequestRow";
import { useLeaveStanding } from "@/pages/Leave/hooks/useLeaveStanding";
import { useLeaveEnabled } from "@/pages/Leave/hooks/useLeaveEnabled";
import {
  isWithdrawable,
  useMyLeaveRequests,
} from "@/pages/Leave/hooks/useMyLeaveRequests";
import { LEAVE_CALENDAR_ZONE_LABEL } from "@/pages/Leave/utils/leaveDates";

/**
 * LeaveRequestsPage
 *
 * Everything the signed-in employee has asked for.
 *
 * A list and nothing else. Asking for leave and looking up company holidays
 * both live on the dashboard card, because they are things you do rather than
 * things you read, and putting them here too would be two places to start the
 * same action.
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
  const { isCovered, isLoading: isCoverageLoading } = useLeaveStanding({
    enabled: isEnabled,
  });
  const {
    requests,
    isLoading,
    loadError,
    saveError,
    withdrawingId,
    load,
    withdraw,
  } = useMyLeaveRequests({ enabled: isEnabled });

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
        <span className="text-sm text-muted-foreground">
          {LEAVE_CALENDAR_ZONE_LABEL}
        </span>
      </div>

      {saveError && <p className="text-sm text-red-700">{saveError}</p>}

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
    </div>
  );
};

export default LeaveRequestsPage;
