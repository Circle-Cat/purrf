import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import LedgerRow from "@/pages/LeavePrototype/LedgerRow";
import { LEDGER_PAGE_SIZE } from "@/pages/LeavePrototype/mockData";

/** Radix Select cannot hold an empty value, so "no filter" needs a name. */
export const EVERYONE = "all";

/**
 * OrgLedger
 *
 * Every ledger row in the company, newest first, with one filter: the person.
 * Filtering to one person is how an administrator reads one person's ledger —
 * there is no separate per-person screen, and the Balances tab links here.
 *
 * Each entry is the same row the employee sees on their own Balance history,
 * with the person named above it. Nothing here edits a row; corrections stay
 * on the Balances tab.
 *
 * @param {object} props
 * @param {Array<object>} props.rows - every row, any order
 * @param {Record<number, {name: string|null, ldap: string|null}>} props.people
 * @param {Array<{id: number, name: string}>} props.filterOptions - who is paid
 *   now; a leaver's rows appear under Everyone but they are not listed here
 * @param {number|typeof EVERYONE} props.personId
 * @param {(id: number|typeof EVERYONE) => void} props.onPersonChange
 * @param {number} props.page - 1-based
 * @param {(page: number) => void} props.onPageChange
 * @returns {JSX.Element}
 */
const OrgLedger = ({
  rows,
  people,
  filterOptions,
  personId,
  onPersonChange,
  page,
  onPageChange,
}) => {
  const selected = rows
    .filter((row) => personId === EVERYONE || row.userId === personId)
    .sort((a, b) =>
      a.effectiveDate === b.effectiveDate
        ? b.leaveLedgerId - a.leaveLedgerId
        : b.effectiveDate.localeCompare(a.effectiveDate),
    );
  const totalEntries = selected.length;
  const pageCount = Math.max(1, Math.ceil(totalEntries / LEDGER_PAGE_SIZE));
  const visible = selected.slice(
    (page - 1) * LEDGER_PAGE_SIZE,
    page * LEDGER_PAGE_SIZE,
  );

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Select
          value={String(personId)}
          onValueChange={(value) =>
            onPersonChange(value === EVERYONE ? EVERYONE : Number(value))
          }
        >
          <SelectTrigger className="w-64" aria-label="Person">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={EVERYONE}>Everyone</SelectItem>
            {filterOptions.map((p) => (
              <SelectItem key={p.id} value={String(p.id)}>
                {p.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <p className="text-sm text-slate-500">
          Entries are only ever added — a correction is a new line, never an
          edit to an old one.
        </p>
      </div>

      {totalEntries === 0 ? (
        <Card className="p-10 text-center">
          <p className="text-sm text-slate-600">
            No ledger entries for this person yet.
          </p>
        </Card>
      ) : (
        <Card className="px-5 py-2">
          <ul className="divide-y divide-slate-100">
            {visible.map((row) => (
              <LedgerRow
                key={row.leaveLedgerId}
                row={row}
                person={{ userId: row.userId, ...people[row.userId] }}
              />
            ))}
          </ul>
        </Card>
      )}

      <div className="flex flex-wrap items-center justify-between gap-3 text-sm text-slate-500">
        {/* Named once here rather than on every row. The real page reads
            LEAVE_CALENDAR_ZONE_LABEL; this public prototype does not name the
            zone. */}
        <span>
          Dates are company business dates, the same for every viewer.
        </span>
        {totalEntries > 0 && (
          <div className="flex items-center gap-3">
            <span className="tabular-nums">
              Page {page} of {pageCount} · {totalEntries}{" "}
              {totalEntries === 1 ? "entry" : "entries"}
            </span>
            <Button
              variant="outline"
              size="sm"
              disabled={page <= 1}
              onClick={() => onPageChange(page - 1)}
            >
              Previous
            </Button>
            <Button
              variant="outline"
              size="sm"
              disabled={page >= pageCount}
              onClick={() => onPageChange(page + 1)}
            >
              Next
            </Button>
          </div>
        )}
      </div>
    </div>
  );
};

export default OrgLedger;
