import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import StateChips from "@/pages/AdminAccounts/components/StateChips";

// Deliberate near-duplicate of
// frontend/src/pages/AdminPermissions/components/UserList.jsx. The two pages
// answer different questions -- who may do what, versus who may sign in at
// all -- and share no state and no row actions. The person columns match that
// page on purpose, because rendering the three names separately is one product
// rule for every admin surface; keeping one component for both would still
// couple two surfaces that are expected to drift, so this copy belongs to the
// account console alone.

const SELECT_CLASS =
  "rounded-md border border-slate-300 bg-white p-2 text-sm text-slate-900";

/**
 * The account console list: search box, Type and Status filters, one row per
 * account with its state chips, and Prev/Next pagination. Purely
 * presentational -- every input and page number lives in useAccountAdmin, so
 * opening a person and coming back lands on the same list.
 *
 * @param {Object} props
 * @param {Array} props.accounts - UserAccountRowDto rows for this page.
 * @param {number} props.total - Row count across all pages.
 * @param {boolean} props.loading
 * @param {string} props.search - Draft search text (not yet submitted).
 * @param {(value: string) => void} props.onSearchChange
 * @param {() => void} props.onSearchSubmit - Commit the draft search text.
 * @param {string} props.userType - "internal"|"external"|"" (all).
 * @param {(value: string) => void} props.onUserTypeChange
 * @param {string} props.status - "active"|"deactivated"|"blocked"|"" (all).
 * @param {(value: string) => void} props.onStatusChange
 * @param {number} props.offset
 * @param {number} props.limit
 * @param {() => void} props.onPrev
 * @param {() => void} props.onNext
 * @param {(account: Object) => void} props.onOpen - Open one account's detail.
 * @param {number|null} props.focusedUserId - The row the viewer just came back
 *   from, marked with data-focused so it can be found again.
 * @param {boolean} props.filtersDisabled - True while the list is a fixed set
 *   of ids rather than a query, so the controls cannot apply. They stay
 *   visible and keep their values, because leaving this mode restores them.
 * @param {boolean} props.paginated - False while the list is showing the
 *   caller's pending block requests, which are not a page of the full list.
 */
const AccountList = ({
  accounts,
  total,
  loading,
  search,
  onSearchChange,
  onSearchSubmit,
  userType,
  onUserTypeChange,
  status,
  onStatusChange,
  offset,
  limit,
  onPrev,
  onNext,
  onOpen,
  focusedUserId,
  filtersDisabled = false,
  paginated = true,
}) => {
  const hasPrev = offset > 0;
  const hasNext = offset + limit < total;

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-end gap-3">
        <Input
          className="w-80"
          placeholder="Name, email, or block reason"
          aria-label="Search accounts"
          value={search}
          disabled={filtersDisabled}
          onChange={(e) => onSearchChange(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && onSearchSubmit()}
        />

        <div className="flex flex-col gap-1">
          <Label htmlFor="account-type-filter">Type</Label>
          <select
            id="account-type-filter"
            className={SELECT_CLASS}
            value={userType}
            disabled={filtersDisabled}
            onChange={(e) => onUserTypeChange(e.target.value)}
          >
            <option value="">All types</option>
            <option value="internal">Internal</option>
            <option value="external">External</option>
          </select>
        </div>

        <div className="flex flex-col gap-1">
          <Label htmlFor="account-status-filter">Status</Label>
          <select
            id="account-status-filter"
            className={SELECT_CLASS}
            value={status}
            disabled={filtersDisabled}
            onChange={(e) => onStatusChange(e.target.value)}
          >
            <option value="">All statuses</option>
            <option value="active">Active</option>
            <option value="deactivated">Deactivated</option>
            <option value="blocked">Blocked</option>
          </select>
        </div>

        <Button
          type="button"
          onClick={onSearchSubmit}
          disabled={filtersDisabled}
        >
          Search
        </Button>
      </div>

      {filtersDisabled && (
        <p className="text-sm text-muted-foreground">
          Showing the accounts your block requests are about. Search and filters
          do not apply here — leave this view to use them again.
        </p>
      )}

      <div className="overflow-auto rounded-lg border border-slate-200">
        <table className="w-full min-w-fit border-collapse text-sm leading-normal">
          <thead>
            <tr className="bg-muted">
              <th className="border-b border-slate-200 px-4 py-3 text-left font-bold">
                User ID
              </th>
              <th className="border-b border-slate-200 px-4 py-3 text-left font-bold">
                First Name
              </th>
              <th className="border-b border-slate-200 px-4 py-3 text-left font-bold">
                Last Name
              </th>
              <th className="border-b border-slate-200 px-4 py-3 text-left font-bold">
                Preferred Name
              </th>
              <th className="border-b border-slate-200 px-4 py-3 text-left font-bold">
                Primary contact email
              </th>
              <th className="border-b border-slate-200 px-4 py-3 text-left font-bold">
                Type
              </th>
              <th className="border-b border-slate-200 px-4 py-3 text-left font-bold">
                State
              </th>
              <th className="border-b border-slate-200 px-4 py-3 text-left font-bold">
                Account
              </th>
            </tr>
          </thead>
          <tbody>
            {loading || accounts.length === 0 ? (
              <tr>
                <td className="px-4 py-3 text-center" colSpan={8}>
                  {loading ? "Loading accounts…" : "No accounts match."}
                </td>
              </tr>
            ) : (
              accounts.map((a) => (
                <tr
                  key={a.userId}
                  data-testid={`account-row-${a.userId}`}
                  data-focused={String(a.userId === focusedUserId)}
                  className={
                    a.userId === focusedUserId
                      ? "bg-sky-50 ring-2 ring-inset ring-sky-300"
                      : undefined
                  }
                >
                  <td className="border-b border-slate-200 px-4 py-3">
                    {a.userId}
                  </td>
                  <td className="border-b border-slate-200 px-4 py-3">
                    {a.firstName}
                  </td>
                  <td className="border-b border-slate-200 px-4 py-3">
                    {a.lastName}
                  </td>
                  <td className="border-b border-slate-200 px-4 py-3">
                    {a.preferredName ?? "\u2014"}
                  </td>
                  <td className="border-b border-slate-200 px-4 py-3">
                    {a.primaryEmail}
                  </td>
                  <td className="border-b border-slate-200 px-4 py-3">
                    {a.userType === "internal"
                      ? "Internal"
                      : a.userType === "external"
                        ? "External"
                        : a.userType}
                  </td>
                  <td className="border-b border-slate-200 px-4 py-3">
                    <StateChips
                      isActive={a.isActive}
                      isBlocked={a.isBlocked}
                      hasPendingBlockRequest={a.hasPendingBlockRequest}
                    />
                  </td>
                  <td className="border-b border-slate-200 px-4 py-3">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => onOpen(a)}
                      aria-label={`Open account ${a.userId}`}
                    >
                      Open
                    </Button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {paginated && (
        <div className="flex items-center justify-between gap-2 text-sm text-muted-foreground">
          <Button
            variant="outline"
            size="sm"
            onClick={onPrev}
            disabled={!hasPrev}
          >
            Prev
          </Button>
          <span>
            {total === 0 ? 0 : offset + 1}–{Math.min(offset + limit, total)} of{" "}
            {total}
          </span>
          <Button
            variant="outline"
            size="sm"
            onClick={onNext}
            disabled={!hasNext}
          >
            Next
          </Button>
        </div>
      )}
    </div>
  );
};

export default AccountList;
