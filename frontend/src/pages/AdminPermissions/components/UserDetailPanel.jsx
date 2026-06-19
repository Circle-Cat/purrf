import { useState } from "react";
import { useAuth } from "@/context/auth";
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
 * SuperAdminControl, PermissionChecklist, and grant history.
 * Must only be rendered when selectedUser is non-null (the Dialog handles the
 * null/open guard externally).
 *
 * @param {Object} props
 * @param {Object} props.selectedUser - AdminUser (non-null).
 * @param {string[]} props.catalog - Grantable permission names.
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

  const displayName = `${selectedUser.firstName} ${selectedUser.lastName}`;
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

        <details className="admin-history">
          <summary className="cursor-pointer font-medium mb-2">History</summary>
          <GrantHistoryTable history={history} />
        </details>
      </div>
    </>
  );
};

export default UserDetailPanel;
