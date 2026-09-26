import React from "react";
import { ENTRY_TYPE_LABELS } from "@/constants/LeaveRequest"; // 请按你实际的常量路径导入
import { formatBusinessDate } from "@/pages/Leave/utils/leaveDates";

/**
 * BalanceHistoryRow
 *
 * One entry in the balance history ledger.
 * Matches the prototype: title + note on the left, colored hours + date on the right.
 */

const BalanceHistoryRow = ({ entry }) => {
  const displayType = ENTRY_TYPE_LABELS[entry.entryType] || entry.entryType;
  const formattedDate = formatBusinessDate(entry.effectiveDate);

  const value = Number(entry.hours ?? 0);
  const displayHours = entry.hours ?? "0.00";
  const signed = value > 0 ? `+${displayHours}` : displayHours;
  const signClass =
    value > 0
      ? "text-emerald-700"
      : value < 0
        ? "text-rose-600"
        : "text-muted-foreground";

  return (
    <li className="flex items-baseline justify-between gap-4 py-2.5 px-4 sm:px-6">
      <div>
        <span className="text-sm font-medium">{displayType}</span>
        {entry.note && (
          <p className="mt-0.5 text-xs text-muted-foreground">{entry.note}</p>
        )}
      </div>
      <div className="shrink-0 text-right">
        <span className={`text-sm font-medium tabular-nums ${signClass}`}>
          {signed} h
        </span>
        <p className="text-xs tabular-nums text-muted-foreground">
          {formattedDate}
        </p>
      </div>
    </li>
  );
};

export default BalanceHistoryRow;
