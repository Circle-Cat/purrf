import { useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "@/context/auth";
import { ROUTE_PATHS } from "@/constants/RoutePaths";
import { legalName } from "@/utils/userName";
import { PERMISSIONS } from "@/constants/Permissions";
import { useUserPermissions } from "@/pages/AdminPermissions/hooks/useUserPermissions";
import PermissionChecklist from "@/pages/AdminPermissions/components/PermissionChecklist";
import SuperAdminControl from "@/pages/AdminPermissions/components/SuperAdminControl";
import GrantHistoryTable from "@/pages/AdminPermissions/components/GrantHistoryTable";
import {
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

/**
 * Body of the per-user permissions Dialog. Renders the DialogHeader, then the
 * SuperAdminControl, PermissionChecklist, and grant history (capped to its own
 * scroll box so it cannot grow the dialog).
 * Must only be rendered when selectedUser is non-null (the Dialog handles the
 * null/open guard externally).
 *
 * @param {Object} props
 * @param {Object} props.selectedUser - AdminUser (non-null).
 * @param {{name: string, description: string}[]} props.catalog - Grantable permissions with descriptions.
 * @param {() => Promise<void>} props.onMakeSuperAdmin
 * @param {() => Promise<void>} props.onRevokeSuperAdmin
 */
const UserDetailPanel = ({
  selectedUser,
  catalog,
  onMakeSuperAdmin,
  onRevokeSuperAdmin,
}) => {
  const { user, isSuperAdmin, permissions } = useAuth();
  const canOpenAccountConsole = permissions.includes(PERMISSIONS.USER_ADMIN);
  const [saving, setSaving] = useState(false);
  const [superBusy, setSuperBusy] = useState(false);
  const { active, history, loading, saveDiff } = useUserPermissions(
    selectedUser.userId,
  );

  const handleSave = async (checked) => {
    setSaving(true);
    try {
      await saveDiff(checked);
    } finally {
      setSaving(false);
    }
  };

  const wrapSuper = (fn) => async () => {
    setSuperBusy(true);
    try {
      await fn();
    } finally {
      setSuperBusy(false);
    }
  };

  // The dialog title has room for one line, so it carries the legal name
  // and the preferred name follows on the sub-line -- all three fields, shown
  // verbatim, which is the rule for an admin view.
  const displayName = legalName(selectedUser);
  const subLine = [
    selectedUser.preferredName ? `"${selectedUser.preferredName}"` : null,
    selectedUser.primaryEmail,
  ]
    .filter(Boolean)
    .join(" · ");

  return (
    <>
      <DialogHeader>
        <DialogTitle>{displayName}</DialogTitle>
        {subLine && <DialogDescription>{subLine}</DialogDescription>}
        {/* The account console holds the other half of this person: whether
            they can sign in at all. The two pages are deliberately separate,
            so each one links to the other -- and the two permissions are held
            by different people, so the crossing is offered only to a viewer
            who holds the far side too. */}
        {canOpenAccountConsole && (
          <Link
            to={`${ROUTE_PATHS.ADMIN_ACCOUNTS}?user_id=${selectedUser.userId}`}
            className="text-sm font-medium text-sky-700 hover:text-sky-900"
          >
            Account state →
          </Link>
        )}
      </DialogHeader>

      <div className="flex flex-col gap-5">
        <SuperAdminControl
          targetIsSuperAdmin={selectedUser.isSuperAdmin}
          callerIsSuperAdmin={isSuperAdmin}
          callerCanRevoke={permissions.includes(PERMISSIONS.SUPER_ADMIN_REVOKE)}
          isSelf={user?.userId === selectedUser.userId}
          busy={superBusy}
          onGrant={wrapSuper(onMakeSuperAdmin)}
          onRevoke={wrapSuper(onRevokeSuperAdmin)}
        />

        {loading ? (
          <p>Loading permissions…</p>
        ) : (
          <PermissionChecklist
            catalog={catalog}
            active={active}
            onSave={handleSave}
            saving={saving}
          />
        )}

        {/* History scrolls inside its own box. Without the cap, a long history
            grows the dialog past its max height, so the whole dialog scrolls
            instead — which carries the title and the absolutely-positioned
            close button up out of view. */}
        <details>
          <summary className="cursor-pointer font-medium mb-2">History</summary>
          <div
            className="max-h-64 overflow-y-auto"
            data-testid="history-scroll"
          >
            <GrantHistoryTable history={history} />
          </div>
        </details>
      </div>
    </>
  );
};

export default UserDetailPanel;
