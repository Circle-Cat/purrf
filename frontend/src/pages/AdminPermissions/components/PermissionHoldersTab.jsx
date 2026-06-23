import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import Table from "@/components/common/Table";
import { usePermissionHolders } from "@/pages/AdminPermissions/hooks/usePermissionHolders";

/**
 * Reverse-lookup tab: pick a permission, list who holds it.
 *
 * @param {Object} props
 * @param {string[]} props.catalog - Grantable permission names.
 */
const PermissionHoldersTab = ({ catalog }) => {
  const {
    permissionName,
    setPermissionName,
    includeRevoked,
    setIncludeRevoked,
    submitSearch,
    hasSearched,
    grants,
    loading,
  } = usePermissionHolders();

  const columns = [
    { header: "User ID", accessor: "userId" },
    { header: "Source", accessor: "grantedSource" },
    { header: "By", accessor: "grantedBy" },
    { header: "When", accessor: "grantedTimestamp" },
    { header: "Status", accessor: "status" },
  ];

  const data = (grants ?? []).map((g) => ({
    userId: g.userId,
    grantedSource: g.grantedSource,
    grantedBy: g.grantedBy ?? "—",
    grantedTimestamp: g.grantedTimestamp,
    status: g.isActive ? "active" : "revoked",
  }));

  return (
    <div className="admin-holders-tab flex flex-col gap-4">
      <div className="admin-holders-filters flex items-center gap-3 flex-wrap">
        <Select value={permissionName} onValueChange={setPermissionName}>
          <SelectTrigger aria-label="Permission" className="w-56">
            <SelectValue placeholder="Select a permission…" />
          </SelectTrigger>
          <SelectContent>
            {catalog.map((name) => (
              <SelectItem key={name} value={name}>
                {name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        <label className="flex items-center gap-1.5 text-sm">
          <Checkbox
            checked={includeRevoked}
            onCheckedChange={(v) => setIncludeRevoked(Boolean(v))}
            aria-label="Include revoked"
          />
          <span>Include revoked</span>
        </label>

        <Button type="button" onClick={submitSearch} disabled={!permissionName}>
          Search
        </Button>
      </div>

      {!hasSearched ? (
        <p>Choose a permission and click Search to see who holds it.</p>
      ) : loading ? (
        <p>Loading…</p>
      ) : (
        <Table columns={columns} data={data} />
      )}
    </div>
  );
};

export default PermissionHoldersTab;
