import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { ArrowLeft } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ROUTE_PATHS } from "@/constants/RoutePaths";
import { PERMISSIONS } from "@/constants/Permissions";
import { legalName } from "@/utils/userName";
import {
  formatDateTimeWithZone,
  resolveViewerTimezone,
} from "@/utils/dateTime";
import {
  useAccountDetail,
  PARAM,
} from "@/pages/AdminAccounts/hooks/useAccountAdmin";
import StateChips from "@/pages/AdminAccounts/components/StateChips";
import BlockRequestCard from "@/pages/AdminAccounts/components/BlockRequestCard";
import DeactivateDialog from "@/pages/AdminAccounts/components/DeactivateDialog";
import BlockDialog from "@/pages/AdminAccounts/components/BlockDialog";
import { useAuth } from "@/context/auth/AuthContext";

const SECTION_TITLE =
  "text-xs font-bold uppercase tracking-wide text-slate-500";

/**
 * One label/value line in the state and identity blocks.
 *
 * @param {Object} props
 * @param {string} props.label
 * @param {import("react").ReactNode} props.value
 */
const Field = ({ label, value }) => (
  <div className="flex gap-2 text-sm">
    <span className="w-40 shrink-0 text-slate-500">{label}</span>
    <span className="text-slate-900">{value}</span>
  </div>
);

/**
 * One account, whole. The page is reached with `?user_id=` on the console
 * route and is already behind `user.admin` there, so no action on it carries a
 * second permission gate. The crossing to the permission page is not an action
 * of this page and is shown only to a viewer who may take it.
 *
 * @param {Object} props
 * @param {number} props.userId - The account being viewed.
 */
const AccountDetailPage = ({ userId }) => {
  const [searchParams] = useSearchParams();
  const { user, permissions } = useAuth();
  const canManagePermissions = permissions.includes(
    PERMISSIONS.PERMISSION_MANAGE,
  );
  const tz = resolveViewerTimezone();
  const [deactivateOpen, setDeactivateOpen] = useState(false);
  const [blockOpen, setBlockOpen] = useState(false);

  const {
    account,
    loading,
    notFound,
    signInMethods,
    signInMethodsFailed,
    pendingRequest,
    pendingRequestFailed,
    preflight,
    preflightError,
    loadPreflight,
    submitting,
    deactivate,
    reactivate,
    unblock,
    block,
    decideRequest,
  } = useAccountDetail(userId);

  // The backend refuses these two on yourself (403) -- they would lock you out
  // of the only console that can undo them. Reactivate and unblock carry no
  // such guard on either side, deliberately.
  const isSelf = user?.userId === account?.userId;

  // The way back out keeps the list exactly as it was left -- same search,
  // filters and page -- and swaps the opened account for `focus`, which only
  // rings that row instead of filtering the list down to it.
  const backParams = new URLSearchParams(searchParams);
  backParams.delete(PARAM.USER_ID);
  backParams.set(PARAM.FOCUS, String(userId));
  const backTo = `${ROUTE_PATHS.ADMIN_ACCOUNTS}?${backParams.toString()}`;

  const backLink = (
    <Link
      to={backTo}
      className="inline-flex items-center gap-1 text-sm font-medium text-slate-600 hover:text-slate-900"
    >
      <ArrowLeft className="h-4 w-4" aria-hidden />
      Accounts
    </Link>
  );

  if (loading) {
    return (
      <div className="flex flex-col gap-4 p-5">
        {backLink}
        <p className="text-sm text-slate-500">Loading account…</p>
      </div>
    );
  }

  if (notFound || !account) {
    return (
      <div className="flex flex-col gap-4 p-5">
        {backLink}
        <p className="text-sm text-slate-500">
          No account with user ID {userId}.
        </p>
      </div>
    );
  }

  const identities = signInMethods?.identities ?? [];
  const emails = signInMethods?.emails ?? [];

  const openBlockDialog = () => {
    setBlockOpen(true);
    loadPreflight();
  };

  const handleDeactivate = async (note) => {
    if (await deactivate(note)) setDeactivateOpen(false);
  };

  const handleBlock = async ({ reason }) => {
    if (await block({ reason })) setBlockOpen(false);
  };

  return (
    <div className="flex flex-col gap-6 p-5">
      {backLink}

      <header className="flex flex-col gap-2">
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="text-xl font-bold text-slate-900">
            {legalName(account)}
          </h1>
          <StateChips
            isActive={account.isActive}
            isBlocked={account.isBlocked}
            hasPendingBlockRequest={account.hasPendingBlockRequest}
          />
        </div>
        <p className="text-sm text-slate-600">
          {[
            account.preferredName ? `"${account.preferredName}"` : null,
            account.primaryEmail,
            `User ID ${account.userId}`,
            account.userType === "internal" ? "Internal" : "External",
            account.isSuperAdmin ? "Super-admin" : null,
          ]
            .filter(Boolean)
            .join(" · ")}
        </p>
      </header>

      {pendingRequestFailed && account.hasPendingBlockRequest && (
        // The chip comes from the account read and says a request exists; the
        // request itself comes from a read that failed. Without this the page
        // shows the chip, no card, and no reason -- and the Block button
        // beside it would close that undecided request as superseded.
        <section className="rounded-lg border border-amber-300 bg-amber-50 p-4 text-sm text-amber-900">
          A block request about this person is waiting on you, but it
          couldn&apos;t be loaded. Reload before acting on this account.
        </section>
      )}

      {pendingRequest && (
        <BlockRequestCard
          request={pendingRequest}
          submitting={submitting}
          onApprove={(note) => decideRequest(true, note)}
          onReject={(note) => decideRequest(false, note)}
        />
      )}

      <section className="flex flex-col gap-2">
        <h2 className={SECTION_TITLE}>Account state</h2>
        <Field
          label="Access"
          value={account.isActive ? "Active" : "Deactivated"}
        />
        {!account.isActive && (
          <>
            <Field
              label="Deactivated"
              value={formatDateTimeWithZone(account.deactivatedAt, tz) ?? "—"}
            />
            <Field
              label="Deactivated by"
              value={account.deactivatedByName ?? "—"}
            />
            <Field label="Note" value={account.deactivatedReason ?? "—"} />
          </>
        )}
        <Field label="Blocked" value={account.isBlocked ? "Yes" : "No"} />
        {account.isBlocked && (
          <>
            <Field
              label="Blocked at"
              value={formatDateTimeWithZone(account.blockedAt, tz) ?? "—"}
            />
            <Field label="Blocked by" value={account.blockedByName ?? "—"} />
            <Field label="Reason" value={account.blockedReason ?? "—"} />
          </>
        )}
      </section>

      <section className="flex flex-col gap-3">
        <h2 className={SECTION_TITLE}>Sign-in methods</h2>
        <p className="text-xs text-slate-500">
          Read-only. Changing how someone signs in is theirs to do, not an
          operator&apos;s.
        </p>

        <div className="flex flex-col gap-1">
          <h3 className="text-sm font-medium text-slate-700">
            Email addresses
          </h3>
          {signInMethodsFailed ? (
            <p className="text-sm text-slate-500">
              Couldn&apos;t read this account&apos;s sign-in methods.
            </p>
          ) : emails.length === 0 ? (
            <p className="text-sm text-slate-500">
              No sign-in address on file.
            </p>
          ) : (
            <ul className="flex flex-col gap-1">
              {emails.map((e) => (
                <li key={e.email} className="text-sm text-slate-900">
                  {e.email}
                  <span className="text-slate-500">
                    {" · "}
                    {e.isPrimary ? "Primary" : "Alternative"}
                    {" · "}
                    {e.otpConfirmed ? "Confirmed" : "Not confirmed"}
                    {e.lastLoginAt
                      ? ` · last signed in ${formatDateTimeWithZone(e.lastLoginAt, tz)}`
                      : " · never signed in"}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="flex flex-col gap-1">
          <h3 className="text-sm font-medium text-slate-700">
            Linked identities
          </h3>
          {signInMethodsFailed ? (
            <p className="text-sm text-slate-500">
              Couldn&apos;t read this account&apos;s sign-in methods.
            </p>
          ) : identities.length === 0 ? (
            // Never a blank section, and never an unearned claim either: this
            // sentence is a fact about the person, so it may only be shown
            // when the read that establishes it actually succeeded.
            <p className="text-sm text-slate-500">
              No linked identity — this account has only ever signed in with an
              email code.
            </p>
          ) : (
            <ul className="flex flex-col gap-1">
              {identities.map((i) => (
                <li
                  key={i.subjectIdentifier}
                  className="text-sm text-slate-900"
                >
                  {i.emailClaim ?? i.subjectIdentifier}
                  <span className="text-slate-500">
                    {" · "}
                    linked {formatDateTimeWithZone(i.linkedAt, tz)}
                    {i.lastLoginAt
                      ? ` · last signed in ${formatDateTimeWithZone(i.lastLoginAt, tz)}`
                      : " · never signed in"}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </section>

      <section className="flex flex-col gap-2">
        <h2 className={SECTION_TITLE}>Actions</h2>
        <div className="flex flex-wrap gap-2">
          {account.isActive ? (
            <Button
              variant="outline"
              onClick={() => setDeactivateOpen(true)}
              disabled={submitting || isSelf}
              title={
                isSelf ? "You cannot deactivate your own account" : undefined
              }
            >
              Deactivate
            </Button>
          ) : (
            <Button
              variant="outline"
              onClick={reactivate}
              disabled={submitting}
            >
              Reactivate
            </Button>
          )}
          {account.isBlocked ? (
            <Button variant="outline" onClick={unblock} disabled={submitting}>
              Unblock
            </Button>
          ) : (
            <Button
              variant="destructive"
              onClick={openBlockDialog}
              disabled={submitting || isSelf}
              title={isSelf ? "You cannot block your own account" : undefined}
            >
              Block
            </Button>
          )}
        </div>
      </section>

      {/* The permission page runs its own gate, so the link was never a way
          in -- but to a viewer without permission.manage it is an offer that
          only leads to a full-page 403. The heading lives inside the check
          because the link is all the section holds. */}
      {canManagePermissions && (
        <section className="flex flex-col gap-2">
          <h2 className={SECTION_TITLE}>Permissions</h2>
          <Link
            to={`${ROUTE_PATHS.ADMIN_USERS}?user_id=${account.userId}`}
            className="text-sm font-medium text-sky-700 hover:text-sky-900"
          >
            Manage permissions →
          </Link>
        </section>
      )}

      <DeactivateDialog
        open={deactivateOpen}
        onOpenChange={setDeactivateOpen}
        account={account}
        onConfirm={handleDeactivate}
        submitting={submitting}
      />
      <BlockDialog
        open={blockOpen}
        onOpenChange={setBlockOpen}
        mode="direct"
        account={account}
        preflight={preflight}
        preflightError={Boolean(preflightError)}
        holders={[]}
        currentUserId={user?.userId}
        onConfirm={handleBlock}
        submitting={submitting}
      />
    </div>
  );
};

export default AccountDetailPage;
