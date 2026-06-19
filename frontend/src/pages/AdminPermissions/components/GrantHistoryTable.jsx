import Table from "@/components/common/Table";
import { displayPermission } from "@/pages/AdminPermissions/utils/permissionLabels";

/**
 * Read-only table of a user's grant/revoke history inside the permissions modal.
 *
 * @param {Object} props
 * @param {Array} props.history - Grant[] (active + revoked rows).
 */
const GrantHistoryTable = ({ history }) => {
  const columns = [
    { header: "Permission", accessor: "permission" },
    { header: "Action", accessor: "action" },
    { header: "Source", accessor: "grantedSource" },
    { header: "By", accessor: "by" },
    { header: "When", accessor: "when" },
  ];

  const data = (history ?? []).map((g) => ({
    permission: displayPermission(g.permissionName),
    action: g.isActive ? "granted" : "revoked",
    grantedSource: g.grantedSource,
    by: g.isActive ? (g.grantedBy ?? "—") : (g.revokedBy ?? "—"),
    when: g.isActive ? g.grantedTimestamp : g.revokedTimestamp,
  }));

  if (!history || history.length === 0) {
    return <p className="text-muted-foreground text-sm">No history</p>;
  }

  return <Table columns={columns} data={data} />;
};

export default GrantHistoryTable;
