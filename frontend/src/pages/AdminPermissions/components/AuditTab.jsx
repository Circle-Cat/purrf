import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import Table from "@/components/common/Table";
import { displayPermission } from "@/pages/AdminPermissions/utils/permissionLabels";
import { useAuditLog } from "@/pages/AdminPermissions/hooks/useAuditLog";

const ALL = "__all__";

/**
 * Read-only permission-change audit feed with filters + pagination.
 *
 * @param {Object} props
 * @param {string[]} props.catalog - Grantable permission names (for the filter).
 */
const AuditTab = ({ catalog }) => {
  const {
    entries,
    total,
    loading,
    hasSearched,
    filters,
    setFilter,
    submitSearch,
    offset,
    limit,
    nextPage,
    prevPage,
  } = useAuditLog();

  const hasPrev = offset > 0;
  const hasNext = offset + limit < total;

  const columns = [
    { header: "When", accessor: "when" },
    { header: "User", accessor: "userId" },
    { header: "Permission", accessor: "permission" },
    { header: "Action", accessor: "action" },
    { header: "Source", accessor: "grantedSource" },
    { header: "By", accessor: "by" },
  ];

  const data = loading
    ? []
    : entries.map((g) => ({
        when: g.isActive ? g.grantedTimestamp : g.revokedTimestamp,
        userId: g.userId,
        permission: displayPermission(g.permissionName),
        action: g.isActive ? "granted" : "revoked",
        grantedSource: g.grantedSource,
        by: g.isActive ? (g.grantedBy ?? "—") : (g.revokedBy ?? "—"),
      }));

  return (
    <div className="admin-audit-tab flex flex-col gap-4">
      <div className="admin-audit-filters flex items-center gap-3 flex-wrap">
        <Input
          className="w-56"
          inputMode="numeric"
          placeholder="User ID"
          value={filters.userId}
          onChange={(e) =>
            setFilter("userId", e.target.value.replace(/\D/g, ""))
          }
          onKeyDown={(e) => e.key === "Enter" && submitSearch()}
        />

        <Select
          value={filters.permissionName || ALL}
          onValueChange={(v) => setFilter("permissionName", v === ALL ? "" : v)}
        >
          <SelectTrigger aria-label="Permission" className="w-56">
            <SelectValue placeholder="All permissions" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>All permissions</SelectItem>
            {catalog.map((name) => (
              <SelectItem key={name} value={name}>
                {name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        <Select
          value={filters.action || ALL}
          onValueChange={(v) => setFilter("action", v === ALL ? "" : v)}
        >
          <SelectTrigger aria-label="Action" className="w-56">
            <SelectValue placeholder="All actions" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>All actions</SelectItem>
            <SelectItem value="granted">granted</SelectItem>
            <SelectItem value="revoked">revoked</SelectItem>
          </SelectContent>
        </Select>

        <Button type="button" onClick={submitSearch}>
          Search
        </Button>
      </div>

      {!hasSearched ? (
        <p className="text-sm text-muted-foreground">
          Set filters and click Search to load the audit log.
        </p>
      ) : (
        <>
          <Table columns={columns} data={data} />

          <div className="admin-audit-pager flex items-center gap-2 text-sm text-muted-foreground">
            <Button
              variant="outline"
              size="sm"
              onClick={prevPage}
              disabled={!hasPrev}
            >
              Prev
            </Button>
            <span>
              {total === 0 ? 0 : offset + 1}–{Math.min(offset + limit, total)}{" "}
              of {total}
            </span>
            <Button
              variant="outline"
              size="sm"
              onClick={nextPage}
              disabled={!hasNext}
            >
              Next
            </Button>
          </div>
        </>
      )}
    </div>
  );
};

export default AuditTab;
