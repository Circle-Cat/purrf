import { Navigate } from "react-router-dom";
import React, { useState } from "react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ROUTE_PATHS } from "@/constants/RoutePaths";
import LeaveBalancesPanel from "@/pages/Leave/BalancesPage";
import LeaveCalendarPanel from "@/pages/Leave/CalendarAdminPage";
import { useLeaveEnabled } from "@/pages/Leave/hooks/useLeaveEnabled";
import LedgerPage from "@/pages/Leave/LedgerPage";

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
  const { isEnabled, isReady } = useLeaveEnabled();

  const [tab, setTab] = useState("balances");
  const [ledgerUserId, setLedgerUserId] = useState(null);
  const [ledgerPage, setLedgerPage] = useState(1);

  if (!isReady) {
    return null;
  }

  if (!isEnabled) {
    return <Navigate to={ROUTE_PATHS.PERSONAL_DASHBOARD} replace />;
  }

  const handleViewHistory = (userId) => {
    setLedgerUserId(userId);
    setLedgerPage(1);
    setTab("ledger");
  };

  const handleLedgerUserChange = (userId) => {
    setLedgerUserId(userId);
    setLedgerPage(1);
  };

  return (
    <div className="space-y-5">
      <h2 className="m-0 text-lg font-medium">Leave administration</h2>
      <Tabs onValueChange={setTab} value={tab}>
        <TabsList>
          <TabsTrigger value="balances">Balances</TabsTrigger>
          <TabsTrigger value="calendar">Yearly setup</TabsTrigger>
          <TabsTrigger value="ledger">Ledger</TabsTrigger>
        </TabsList>

        <TabsContent value="balances" className="pt-4">
          <LeaveBalancesPanel onViewHistory={handleViewHistory} />
        </TabsContent>

        <TabsContent value="calendar" className="pt-4">
          <LeaveCalendarPanel />
        </TabsContent>
        <TabsContent value="ledger" className="pt-4">
          <LedgerPage
            userId={ledgerUserId}
            page={ledgerPage}
            onUserChange={handleLedgerUserChange}
            onPageChange={setLedgerPage}
          />
        </TabsContent>
      </Tabs>
    </div>
  );
};

export default LeaveAdminPage;
