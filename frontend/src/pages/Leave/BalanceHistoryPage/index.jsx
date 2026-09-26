import { Navigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { useLeaveStanding } from "@/pages/Leave/hooks/useLeaveStanding";
import { useLeaveEnabled } from "@/pages/Leave/hooks/useLeaveEnabled";
import { ROUTE_PATHS } from "@/constants/RoutePaths";
import { useMyLeaveLedger } from "@/pages/Leave/hooks/useMyLeaveLedger";
import BalanceHistoryRow from "@/pages/Leave/BalanceHistoryPage/components/BalanceHistoryRow";
import { LEAVE_CALENDAR_ZONE_LABEL } from "@/pages/Leave/utils/leaveDates";

export default function BalanceHistoryPage() {
  const isEnabled = useLeaveEnabled();

  const { isCovered, isLoading: isStandingLoading } = useLeaveStanding({
    enabled: isEnabled,
  });

  const {
    data: ledgerData,
    isLoading: isLedgerLoading,
    loadError,
    load,
  } = useMyLeaveLedger({
    enabled: isEnabled && isCovered,
  });

  if (!isEnabled) {
    return <Navigate to={ROUTE_PATHS.PERSONAL_DASHBOARD} replace />;
  }

  if (isStandingLoading) {
    return (
      <div className="p-6 text-sm text-muted-foreground">
        Loading balance history...
      </div>
    );
  }

  if (!isCovered) {
    return (
      <div className="p-6 text-sm text-muted-foreground">
        Leave isn't tracked for your account.
      </div>
    );
  }

  if (isLedgerLoading) {
    return (
      <div className="p-6 text-sm text-muted-foreground">
        Loading balance history...
      </div>
    );
  }

  if (loadError) {
    return (
      <div className="flex flex-col items-start gap-3 p-6">
        <p className="text-sm text-muted-foreground">
          Failed to load balance history.
        </p>
        <Button variant="link" onClick={() => load()}>
          Retry
        </Button>
      </div>
    );
  }

  const balanceHours = Number(ledgerData?.balanceHours ?? 0).toFixed(2);
  const entries = ledgerData?.entries ?? [];

  return (
    <div className="space-y-5">
      {/* Heading + timezone (outside the card) */}
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <h2 className="m-0 text-lg font-bold">Balance history</h2>
        <span className="text-sm text-muted-foreground">
          {LEAVE_CALENDAR_ZONE_LABEL}
        </span>
      </div>

      <p className="text-sm text-muted-foreground">
        Entries are only ever added — a correction is a new line, never an edit
        to an old one.
      </p>

      <Card className="border-gray-200 shadow-sm">
        {entries.length === 0 ? (
          <div className="p-6 text-center text-sm text-muted-foreground">
            No balance history entries found.
          </div>
        ) : (
          <>
            <ul className="divide-y divide-gray-100">
              {entries.map((entry, index) => (
                <BalanceHistoryRow key={entry.id ?? index} entry={entry} />
              ))}
            </ul>

            <div className="flex justify-between border-t border-gray-200 py-3 px-4 sm:px-6 font-bold">
              <span className="text-sm">Total on record</span>
              <span className="text-sm font-mono tabular-nums">
                {balanceHours} h
              </span>
            </div>
          </>
        )}
      </Card>
    </div>
  );
}
