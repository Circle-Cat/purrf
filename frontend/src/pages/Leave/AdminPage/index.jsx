import { Navigate } from "react-router-dom";

import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ROUTE_PATHS } from "@/constants/RoutePaths";
import LeaveBalancesPanel from "@/pages/Leave/BalancesPage";
import LeaveCalendarPanel from "@/pages/Leave/CalendarAdminPage";
import { useLeaveEnabled } from "@/pages/Leave/hooks/useLeaveEnabled";

/**
 * LeaveAdminPage
 *
 * The administrative side of leave, in one place: entering the year's company
 * holidays, and everybody's balances.
 *
 * One page with two tabs rather than two sidebar entries. Both are the same
 * job -- keeping the engine's inputs right -- and separating them in the
 * navigation invited reading "Leave Balances" as somebody's own balance, which
 * is a different screen entirely and belongs on the dashboard.
 *
 * @returns {JSX.Element}
 */
const LeaveAdminPage = () => {
  const isEnabled = useLeaveEnabled();

  if (!isEnabled) {
    return <Navigate to={ROUTE_PATHS.PERSONAL_DASHBOARD} replace />;
  }

  return (
    <div className="space-y-5">
      <h2 className="m-0 text-lg font-medium">Leave administration</h2>
      <Tabs defaultValue="balances">
        <TabsList>
          <TabsTrigger value="balances">Balances</TabsTrigger>
          <TabsTrigger value="calendar">Yearly setup</TabsTrigger>
        </TabsList>
        <TabsContent value="balances" className="pt-4">
          <LeaveBalancesPanel />
        </TabsContent>
        <TabsContent value="calendar" className="pt-4">
          <LeaveCalendarPanel />
        </TabsContent>
      </Tabs>
    </div>
  );
};

export default LeaveAdminPage;
