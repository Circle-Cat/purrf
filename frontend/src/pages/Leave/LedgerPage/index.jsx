import React from "react";
import BalanceHistoryRow from "@/pages/Leave/components/BalanceHistoryRow";
import { useLeaveLedger } from "@/pages/Leave/hooks/useLeaveLedger";

const PAGE_SIZE = 50;

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

  const personMap = React.useMemo(() => {
    const map = new Map();
    people.forEach((p) => {
      if (p.id) map.set(p.id, p);
      if (p.userId) map.set(p.userId, p);
    });
    return map;
  }, [people]);

  const totalPages = Math.ceil(totalEntries / PAGE_SIZE) || 1;
  const hasPrev = page > 1;
  const hasNext = page < totalPages;

  return (
    <div className="space-y-4 py-4">
      {/* 1. Person Select Filter */}
      <div className="flex items-center justify-between gap-4">
        <div className="flex items-center gap-2">
          <label htmlFor="ledger-person-select" className="text-sm font-medium">
            Filter by Person:
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
            <option value="">All Employees</option>
            {people.map((p) => (
              <option key={p.id || p.userId} value={p.id || p.userId}>
                {p.name} ({p.ldap})
              </option>
            ))}
          </select>
        </div>

        <div className="text-xs text-muted-foreground">
          Showing {entries.length} of {totalEntries} entries
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
            {entries.map((entry) => {
              const entryUserId = entry.userId ?? entry.user_id;
              const person = entryUserId ? personMap.get(entryUserId) : null;
              return (
                <BalanceHistoryRow
                  key={entry.entryId || entry.id}
                  entry={entry}
                  person={person}
                />
              );
            })}
          </ul>
        )}
      </div>

      {/* 3. Prev/Next Pager */}
      <div className="flex items-center justify-between pt-2">
        <span className="text-xs text-muted-foreground">
          Page {page} of {totalPages}
        </span>
        <div className="flex items-center gap-2">
          <button
            type="button"
            disabled={!hasPrev || isLoading}
            onClick={() => onPageChange(page - 1)}
            className="inline-flex items-center justify-center rounded-md border border-input bg-background px-3 py-1.5 text-xs font-medium shadow-sm transition-colors hover:bg-accent disabled:pointer-events-none disabled:opacity-50"
          >
            Previous
          </button>
          <button
            type="button"
            disabled={!hasNext || isLoading}
            onClick={() => onPageChange(page + 1)}
            className="inline-flex items-center justify-center rounded-md border border-input bg-background px-3 py-1.5 text-xs font-medium shadow-sm transition-colors hover:bg-accent disabled:pointer-events-none disabled:opacity-50"
          >
            Next
          </button>
        </div>
      </div>
    </div>
  );
}
