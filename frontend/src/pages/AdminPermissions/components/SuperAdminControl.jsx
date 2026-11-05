import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

/**
 * Super-admin status + action, gated to mirror the backend exactly:
 * - target not super-admin -> "Make super-admin", only if the caller is a
 *   super-admin (else the backend would 403).
 * - target is super-admin  -> "Revoke super-admin", only if the caller holds
 *   SUPER_ADMIN_REVOKE, and disabled when acting on yourself (backend 400).
 *
 * @param {Object} props
 * @param {boolean} props.targetIsSuperAdmin
 * @param {boolean} props.callerIsSuperAdmin
 * @param {boolean} props.callerCanRevoke
 * @param {boolean} props.isSelf
 * @param {boolean} props.busy
 * @param {() => void} props.onGrant
 * @param {() => void} props.onRevoke
 */
const SuperAdminControl = ({
  targetIsSuperAdmin,
  callerIsSuperAdmin,
  callerCanRevoke,
  isSelf,
  busy,
  onGrant,
  onRevoke,
}) => {
  return (
    <div className="admin-super-admin-control flex items-center gap-2.5 pb-4 border-b">
      <span>Super-admin:</span>
      {targetIsSuperAdmin ? <Badge>Yes</Badge> : <span>No</span>}

      {!targetIsSuperAdmin && callerIsSuperAdmin && (
        <Button size="sm" onClick={onGrant} disabled={busy}>
          Make super-admin
        </Button>
      )}

      {targetIsSuperAdmin && callerCanRevoke && (
        <Button
          size="sm"
          variant="destructive"
          onClick={onRevoke}
          disabled={busy || isSelf}
          title={isSelf ? "You cannot revoke your own super-admin" : undefined}
        >
          Revoke super-admin
        </Button>
      )}
    </div>
  );
};

export default SuperAdminControl;
