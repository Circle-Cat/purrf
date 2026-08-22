import { Navigate } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import ApprovalRow from "@/pages/Leave/ApprovalsPage/components/ApprovalRow";
import { useLeaveApprovals } from "@/pages/Leave/hooks/useLeaveApprovals";
import { useLeaveEnabled } from "@/pages/Leave/hooks/useLeaveEnabled";
import { LEAVE_CALENDAR_ZONE_LABEL } from "@/pages/Leave/utils/leaveDates";
import { ROUTE_PATHS } from "@/constants/RoutePaths";

/**
 * LeaveApprovalsPage
 *
 * The requests other people have filed against the signed-in user: what still
 * needs deciding, and what has already been settled.
 *
 * The settled half is not a nicety. Approval is the end of the line, so once a
 * manager has worked through their queue the only question they are left with
 * is "did I approve that", and this is the one place that answers it.
 *
 * Anyone signed in may open this page. It shows what was filed against them
 * and nothing else, so somebody who approves for nobody sees an empty page
 * rather than being refused -- there is no manager permission to check, and the
 * server decides ownership on every route.
 *
 * Behind the leave feature flag, and the address is covered as well as the entry
 * point: hiding the dashboard card alone would leave the page reachable by
 * anybody who typed its path.
 *
 * @returns {JSX.Element}
 */
const LeaveApprovalsPage = () => {
  const isEnabled = useLeaveEnabled();
  const {
    pending,
    decided,
    isLoading,
    loadError,
    decidingId,
    decideError,
    load,
    decide,
  } = useLeaveApprovals({ enabled: isEnabled });

  if (!isEnabled) {
    return <Navigate to={ROUTE_PATHS.PERSONAL_DASHBOARD} replace />;
  }

  return (
    <div className="space-y-5">
      <div className="flex items-baseline justify-between gap-4">
        <h2 className="m-0 text-lg font-medium">Leave Approvals</h2>
        <span className="text-sm text-muted-foreground">
          {LEAVE_CALENDAR_ZONE_LABEL}
        </span>
      </div>

      {isLoading && <p className="text-sm text-muted-foreground">Loading…</p>}

      {!isLoading && loadError && (
        <div className="flex flex-col items-start gap-3">
          <p className="text-sm text-muted-foreground">
            Couldn't load your approvals.
          </p>
          <Button onClick={load}>Retry</Button>
        </div>
      )}

      {!isLoading && !loadError && (
        <>
          {decideError && (
            <p className="text-sm text-red-700">
              That decision didn't go through. Nothing was recorded — try again.
            </p>
          )}

          <Card className="border-gray-200 shadow-sm">
            <CardHeader>
              <CardTitle className="text-lg font-semibold">
                Waiting on you
              </CardTitle>
            </CardHeader>
            <CardContent>
              {pending.length === 0 ? (
                <p className="text-sm text-muted-foreground">
                  Nothing is waiting on you.
                </p>
              ) : (
                <ul className="divide-y divide-gray-100">
                  {pending.map((row) => (
                    <ApprovalRow
                      key={row.requestId}
                      row={row}
                      isDecidable
                      isDeciding={decidingId !== null}
                      onDecide={decide}
                    />
                  ))}
                </ul>
              )}
            </CardContent>
          </Card>

          <Card className="border-gray-200 shadow-sm">
            <CardHeader>
              <CardTitle className="text-lg font-semibold">Decided</CardTitle>
            </CardHeader>
            <CardContent>
              {decided.length === 0 ? (
                <p className="text-sm text-muted-foreground">
                  Nothing decided yet.
                </p>
              ) : (
                <ul className="divide-y divide-gray-100">
                  {decided.map((row) => (
                    <ApprovalRow
                      key={row.requestId}
                      row={row}
                      isDecidable={false}
                      isDeciding={false}
                    />
                  ))}
                </ul>
              )}
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
};

export default LeaveApprovalsPage;
