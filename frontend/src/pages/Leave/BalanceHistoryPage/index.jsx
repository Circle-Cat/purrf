import { useEffect, useState } from "react";

import { getMyLeaveLedger } from "@/api/leaveApi";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useLeaveStanding } from "@/pages/Leave/hooks/useLeaveStanding";
import {
  formatBusinessDate,
  LEAVE_CALENDAR_ZONE_LABEL,
} from "@/pages/Leave/utils/leaveDates";

const ENTRY_TYPE_LABELS = {
  weekly_accrual: "Weekly Accrual",
  leave_deduction: "Leave Deduction",
  level_change: "Level Change",
  manual_adjustment: "Manual Adjustment",
  exchange_credit: "Exchange Credit",
  carryover_forfeit: "Carryover Forfeit",
};

export default function BalanceHistoryPage() {
  const { isCovered, isLoading: isStandingLoading } = useLeaveStanding();
  const [ledgerData, setLedgerData] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (isCovered) {
      getMyLeaveLedger()
        .then((res) => {
          setLedgerData(res.data || res);
        })
        .catch((err) => {
          setError(err.message || "Failed to load balance history");
        })
        .finally(() => {
          setIsLoading(false);
        });
    } else {
      setIsLoading(false);
    }
  }, [isCovered]);

  if (isStandingLoading || isLoading) {
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

  if (error) {
    return <div className="p-6 text-sm text-rose-600">Error: {error}</div>;
  }

  const balanceHours = ledgerData?.balanceHours ?? "0.00";
  const entries = ledgerData?.entries ?? [];

  return (
    <div className="mx-auto max-w-4xl space-y-6 p-6">
      <Card className="border-gray-200 shadow-sm">
        <CardHeader>
          <CardTitle className="text-xl font-semibold">
            Balance History
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-baseline gap-2">
            <span className="text-sm font-medium text-muted-foreground">
              Current Balance:
            </span>
            <span className="text-3xl font-bold tabular-nums">
              {balanceHours} h
            </span>
          </div>
        </CardContent>
      </Card>

      <Card className="border-gray-200 shadow-sm">
        <CardContent className="p-0">
          {entries.length === 0 ? (
            <div className="p-6 text-center text-sm text-muted-foreground">
              No balance history entries found.
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Effective Date</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead className="text-right">Hours</TableHead>
                  <TableHead>Note</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {entries.map((entry, index) => {
                  const displayType =
                    ENTRY_TYPE_LABELS[entry.entryType] || entry.entryType;

                  return (
                    <TableRow key={index}>
                      <TableCell className="font-mono text-xs">
                        {formatBusinessDate(entry.effectiveDate)}
                      </TableCell>
                      <TableCell className="text-sm">{displayType}</TableCell>
                      <TableCell className="text-right font-mono text-sm tabular-nums">
                        {entry.hours}
                      </TableCell>
                      <TableCell className="text-sm text-muted-foreground">
                        {entry.note || "—"}
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <footer className="text-right text-xs text-muted-foreground">
        {LEAVE_CALENDAR_ZONE_LABEL}
      </footer>
    </div>
  );
}
