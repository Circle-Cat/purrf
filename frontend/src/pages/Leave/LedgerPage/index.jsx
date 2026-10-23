import React from "react";
import BalanceHistoryRow from "@/pages/Leave/components/BalanceHistoryRow";
import { useLeaveLedger } from "@/pages/Leave/hooks/useLeaveLedger";
import { Button } from "@/components/ui/button";

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

  const totalPages = Math.ceil(totalEntries / PAGE_SIZE) || 1;
  const hasPrev = page > 1;
  const hasNext = page < totalPages;

  const allFilterOptions = React.useMemo(() => {
    const map = new Map();

    people.forEach((p) => {
      const id = p.id || p.userId;
      if (id) {
        map.set(id, { id, name: p.name, ldap: p.ldap, isFormer: false });
      }
    });

    entries.forEach((entry) => {
      const uid = entry.userId ?? entry.user_id;
      if (uid && !map.has(uid)) {
        map.set(uid, {
          id: uid,
          name: entry.name || `User ${uid}`,
          ldap: entry.ldap,
          isFormer: true,
        });
      }
    });

    return Array.from(map.values());
  }, [people, entries]);

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
            {allFilterOptions.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name} {p.ldap ? `(${p.ldap})` : ""}{" "}
                {p.isFormer ? " - (Inactive/Left)" : ""}
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
            {entries.map((entry) => (
              <BalanceHistoryRow key={entry.leaveLedgerId} entry={entry} />
            ))}
          </ul>
        )}
      </div>

      {/* 3. Prev/Next Pager */}
      <div className="flex items-center justify-between pt-2">
        <span className="text-xs text-muted-foreground">
          Page {page} of {totalPages}
        </span>
        <div className="flex items-center gap-2">
          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={!hasPrev || isLoading}
            onClick={() => onPageChange(page - 1)}
          >
            Previous
          </Button>
          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={!hasNext || isLoading}
            onClick={() => onPageChange(page + 1)}
          >
            Next
          </Button>
        </div>
      </div>
    </div>
  );
}
