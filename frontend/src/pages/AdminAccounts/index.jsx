import { useSearchParams } from "react-router-dom";
import { Button } from "@/components/ui/button";
import {
  useAccountAdmin,
  PARAM,
} from "@/pages/AdminAccounts/hooks/useAccountAdmin";
import AccountList from "@/pages/AdminAccounts/components/AccountList";
import AccountDetailPage from "@/pages/AdminAccounts/components/AccountDetailPage";

/**
 * The list itself, plus the banner for block requests waiting on the viewer.
 * Split out so the detail view can take over the route without this view's
 * hooks running behind it.
 */
const AccountsListView = () => {
  const {
    accounts,
    total,
    loading,
    search,
    setSearch,
    submitSearch,
    userType,
    setUserType,
    status,
    setStatus,
    offset,
    limit,
    nextPage,
    prevPage,
    openAccount,
    focusedUserId,
    pendingCount,
    pendingOnly,
    showPendingOnly,
    clearPendingOnly,
  } = useAccountAdmin();

  return (
    <div className="flex flex-col gap-4 p-5">
      <h1 className="text-xl font-bold text-slate-900">Accounts</h1>

      {(pendingCount > 0 || pendingOnly) && (
        // Also rendered when the count is zero but the view is still on:
        // deciding your last request drops the count, and if the banner went
        // with it the way out would go too, leaving an empty table with every
        // control disabled and nothing to leave by.
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-amber-300 bg-amber-50 px-4 py-3">
          <p className="text-sm font-medium text-amber-900">
            {pendingCount === 0
              ? "No block requests are waiting on you"
              : `${pendingCount} block request${pendingCount === 1 ? "" : "s"} awaiting your decision`}
          </p>
          {pendingOnly ? (
            <Button type="button" variant="outline" onClick={clearPendingOnly}>
              Show all accounts
            </Button>
          ) : (
            <Button type="button" variant="outline" onClick={showPendingOnly}>
              Show them
            </Button>
          )}
        </div>
      )}

      <AccountList
        accounts={accounts}
        total={total}
        loading={loading}
        search={search}
        onSearchChange={setSearch}
        onSearchSubmit={submitSearch}
        userType={userType}
        onUserTypeChange={setUserType}
        status={status}
        onStatusChange={setStatus}
        offset={offset}
        limit={limit}
        onPrev={prevPage}
        onNext={nextPage}
        onOpen={openAccount}
        focusedUserId={focusedUserId}
        filtersDisabled={pendingOnly}
        paginated={!pendingOnly}
      />
    </div>
  );
};

/**
 * Account console. One route, two views: the list, and one account in full
 * when `?user_id=` names somebody. The whole route is gated on `user.admin`,
 * which is why neither view gates anything again.
 *
 * Route: /admin/accounts
 */
const AdminAccounts = () => {
  const [searchParams] = useSearchParams();
  const raw = searchParams.get(PARAM.USER_ID);
  const userId = raw === null ? null : Number.parseInt(raw, 10);

  if (userId !== null && !Number.isNaN(userId)) {
    return <AccountDetailPage userId={userId} />;
  }
  return <AccountsListView />;
};

export default AdminAccounts;
