import React from "react";
import BalanceHistoryRow from "@/pages/Leave/components/BalanceHistoryRow";
import { useLeaveLedger } from "@/pages/Leave/hooks/useLeaveLedger";
import { Button } from "@/components/ui/button";
import { LEAVE_CALENDAR_ZONE_LABEL } from "@/pages/Leave/utils/leaveDates";

const PAGE_SIZE = 50;

const formatOptionLabel = (p) => {
  const rawName = p.name?.trim();
  const displayName = rawName || `User ${p.userId}`;

  const ldapClean = p.ldap?.trim();
  const ldapStr = ldapClean ? `(${ldapClean})` : "";

  return [displayName, ldapStr].filter(Boolean).join(" ");
};

/**
 * LedgerPage / LedgerTab
 *
 * Renders the administrator's leave balance ledger tab:
 * - Person Select dropdown (All employees vs specific user)
 * - Balance history rows list
 * - Prev / Next Pager
 */
export default function LedgerPage({
  userId = null,
  page = 1,
  onUserChange,
  onPageChange,
  people = [],
}) {
  const { entries, totalEntries, isLoading, loadError } = useLeaveLedger({
    userId,
    page,
    pageSize: PAGE_SIZE,
  });

  const first = totalEntries === 0 ? 0 : (page - 1) * PAGE_SIZE + 1;
  const last = Math.min(page * PAGE_SIZE, totalEntries);
  const isPrevDisabled = page <= 1 || isLoading;
  const isNextDisabled = page * PAGE_SIZE >= totalEntries || isLoading;

  const allFilterOptions = React.useMemo(() => {
    const map = new Map();

    people.forEach((p) => {
      const id = p.userId;
      if (id) {
        map.set(id, {
          userId: id,
          name: p.name,
          ldap: p.ldap,
        });
      }
    });

    return Array.from(map.values());
  }, [people]);

  return (
    <div className="space-y-4 py-4">
      {/* 1. Person Select Filter */}
      <div className="flex items-center justify-between gap-4">
        <div className="flex items-center gap-2">
          <label htmlFor="ledger-person-select" className="text-sm font-medium">
            Filter by person:
          </label>
          <select
            id="ledger-person-select"
            value={userId ?? ""}
            onChange={(e) => {
              const val = e.target.value;
              onUserChange(val ? Number(val) : null);
            }}
            className="h-9 rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
          >
            <option value="">All employees</option>
            {allFilterOptions.map((p) => (
              <option key={p.userId} value={p.userId}>
                {formatOptionLabel(p)}
              </option>
            ))}
          </select>
        </div>

        <div className="text-sm text-muted-foreground">
          {LEAVE_CALENDAR_ZONE_LABEL}
        </div>
      </div>

      {/* 2. Balance History Rows List */}
      <div className="rounded-md border bg-card text-card-foreground shadow-sm">
        {isLoading ? (
          <div className="p-8 text-center text-sm text-muted-foreground">
            Loading ledger entries...
          </div>
        ) : loadError ? (
          <div className="p-8 text-center text-sm text-rose-600">
            Failed to load ledger history. Please try again.
          </div>
        ) : entries.length === 0 ? (
          <div className="p-8 text-center text-sm text-muted-foreground">
            No balance history entries found.
          </div>
        ) : (
          <ul className="divide-y">
            {entries.map((entry) => (
              <BalanceHistoryRow
                key={entry.leaveLedgerId}
                entry={entry}
                showPerson={true}
              />
            ))}
          </ul>
        )}
      </div>

      {/* 3. Prev/Next Pager */}
      <div className="flex items-center justify-between gap-2 text-sm text-muted-foreground">
        <Button
          type="button"
          variant="outline"
          size="sm"
          disabled={isPrevDisabled}
          onClick={() => onPageChange(page - 1)}
        >
          Prev
        </Button>
        <span>
          {first}–{last} of {totalEntries}
        </span>
        <Button
          type="button"
          variant="outline"
          size="sm"
          disabled={isNextDisabled}
          onClick={() => onPageChange(page + 1)}
        >
          Next
        </Button>
      </div>
    </div>
  );
}
