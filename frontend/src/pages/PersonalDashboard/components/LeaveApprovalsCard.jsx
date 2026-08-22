import { useNavigate } from "react-router-dom";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { ROUTE_PATHS } from "@/constants/RoutePaths";

/**
 * LeaveApprovalsCard
 *
 * The way in to deciding other people's leave, on Personal Dashboard.
 *
 * It sits here rather than in the sidebar because the sidebar is driven
 * entirely by permissions, and approving leave is not one: the manager
 * relationship comes from Azure and no role is built from it. A sidebar entry
 * could therefore only be shown to everybody, which is a dead end for the
 * majority who approve for nobody.
 *
 * This block is independent of whether the viewer gets leave themselves. A
 * manager outside the leave population -- not a full-time employee in scope --
 * still decides their reports' requests, and has no balance of their own to
 * show. So this is a sibling of the employee-facing leave blocks, never nested
 * inside them.
 *
 * The caller decides whether to render it at all; this component assumes the
 * viewer is an approver.
 *
 * @param {{ pendingCount: number }} props
 */
const LeaveApprovalsCard = ({ pendingCount }) => {
  const navigate = useNavigate();

  return (
    <Card className="border-gray-200 shadow-sm">
      <CardHeader>
        <CardTitle className="text-lg font-semibold">Leave Approvals</CardTitle>
      </CardHeader>
      <CardContent className="flex items-center justify-between gap-4">
        <p className="text-sm text-muted-foreground">
          {pendingCount === 0
            ? "Nothing is waiting on you."
            : `${pendingCount} ${
                pendingCount === 1 ? "request is" : "requests are"
              } waiting on your decision.`}
        </p>
        <Button onClick={() => navigate(ROUTE_PATHS.LEAVE_APPROVALS)}>
          {/* The count rides on the button so the answer to "do I need to open
              this" is on the dashboard, not one navigation away. */}
          Review{pendingCount > 0 ? ` (${pendingCount})` : ""}
        </Button>
      </CardContent>
    </Card>
  );
};

export default LeaveApprovalsCard;
