import Table from "@/components/common/Table";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Pencil } from "lucide-react";

/** Sentinel value meaning "no user-type filter". */
const ALL_TYPES = "__all__";

/**
 * Maps table column accessors to backend sort_by field names.
 * @type {Record<string, string>}
 */
const ACCESSOR_TO_SORT_FIELD = {
  userId: "user_id",
  firstName: "first_name",
  lastName: "last_name",
  preferredName: "preferred_name",
  userType: "user_type",
  status: "is_active",
  superAdmin: "is_super_admin",
};

/**
 * Users tab list pane: search box, filter controls, a full-width sortable
 * Table with one row per user, and Prev/Next pagination. Purely presentational
 * — all state lives in useUserAdmin.
 *
 * @param {Object} props
 * @param {Array} props.users
 * @param {number} props.total
 * @param {boolean} props.loading
 * @param {boolean} props.hasSearched - Whether a search has been run yet.
 * @param {string} props.search - Draft name/email search text.
 * @param {(value: string) => void} props.onSearchChange
 * @param {string} props.userId - Draft exact User ID search text (digits only).
 * @param {(value: string) => void} props.onUserIdChange
 * @param {() => void} props.onSearch - Commit the draft inputs and search.
 * @param {number} props.offset
 * @param {number} props.limit
 * @param {() => void} props.onPrev
 * @param {() => void} props.onNext
 * @param {(user: Object) => void} props.onSelect
 * @param {string|null} props.sortBy - Active backend sort field (e.g. "last_name").
 * @param {"asc"|"desc"} props.order - Current sort direction.
 * @param {(field: string) => void} props.onToggleSort - Called with backend field name.
 * @param {boolean} props.isSuperAdmin - Super-admins-only filter (draft).
 * @param {(checked: boolean) => void} props.onSuperAdminFilterChange
 * @param {string} props.userType - "internal"|"external"|"" (all) (draft).
 * @param {(value: string) => void} props.onUserTypeChange
 */
const UserList = ({
  users,
  total,
  loading,
  hasSearched,
  search,
  onSearchChange,
  userId,
  onUserIdChange,
  onSearch,
  offset,
  limit,
  onPrev,
  onNext,
  onSelect,
  sortBy,
  order,
  onToggleSort,
  isSuperAdmin,
  onSuperAdminFilterChange,
  userType,
  onUserTypeChange,
}) => {
  const hasPrev = offset > 0;
  const hasNext = offset + limit < total;

  // Reverse-lookup: find the accessor whose mapped backend field matches sortBy.
  const activeSortAccessor = sortBy
    ? (Object.keys(ACCESSOR_TO_SORT_FIELD).find(
        (acc) => ACCESSOR_TO_SORT_FIELD[acc] === sortBy,
      ) ?? null)
    : null;

  const handleSort = (accessor) => {
    const field = ACCESSOR_TO_SORT_FIELD[accessor];
    if (field && onToggleSort) onToggleSort(field);
  };

  const columns = [
    { header: "User ID", accessor: "userId", sortable: true },
    { header: "First Name", accessor: "firstName", sortable: true },
    { header: "Last Name", accessor: "lastName", sortable: true },
    { header: "Preferred Name", accessor: "preferredName", sortable: true },
    { header: "User Type", accessor: "userType", sortable: true },
    { header: "Status", accessor: "status", sortable: true },
    { header: "Super-admin", accessor: "superAdmin", sortable: true },
    { header: "Actions", accessor: "actions" },
  ];

  const data = loading
    ? []
    : users.map((u) => ({
        userId: u.userId,
        firstName: u.firstName,
        lastName: u.lastName,
        preferredName: u.preferredName ?? "—",
        userType:
          u.userType === "internal"
            ? "Internal"
            : u.userType === "external"
              ? "External"
              : u.userType,
        status: u.isActive ? (
          "Active"
        ) : (
          <Badge variant="secondary">Deactivated</Badge>
        ),
        superAdmin: u.isSuperAdmin ? <Badge>Super-admin</Badge> : "—",
        actions: (
          <Button
            size="icon"
            variant="ghost"
            aria-label="Manage permissions"
            onClick={() => onSelect(u)}
          >
            <Pencil className="size-4" />
          </Button>
        ),
      }));

  return (
    <div className="admin-user-list flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-3">
        <Input
          className="w-64"
          placeholder="Search by name or email…"
          value={search}
          onChange={(e) => onSearchChange(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && onSearch()}
        />

        <Input
          className="w-40"
          inputMode="numeric"
          placeholder="User ID"
          value={userId}
          onChange={(e) => onUserIdChange(e.target.value.replace(/\D/g, ""))}
          onKeyDown={(e) => e.key === "Enter" && onSearch()}
        />

        <label className="flex items-center gap-2 text-sm cursor-pointer select-none">
          <Checkbox
            checked={isSuperAdmin}
            onCheckedChange={onSuperAdminFilterChange}
            aria-label="Super-admins only"
          />
          Super-admins only
        </label>

        <Select
          value={userType || ALL_TYPES}
          onValueChange={(v) => onUserTypeChange(v === ALL_TYPES ? "" : v)}
        >
          <SelectTrigger aria-label="User type" className="w-40">
            <SelectValue placeholder="All types" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL_TYPES}>All types</SelectItem>
            <SelectItem value="internal">Internal</SelectItem>
            <SelectItem value="external">External</SelectItem>
          </SelectContent>
        </Select>

        <Button type="button" onClick={onSearch}>
          Search
        </Button>
      </div>

      {!hasSearched ? (
        <p className="text-sm text-muted-foreground">
          Enter search criteria and click Search.
        </p>
      ) : (
        <>
          <Table
            columns={columns}
            data={data}
            onSort={handleSort}
            sortColumn={activeSortAccessor}
            sortDirection={order}
          />

          <div className="admin-user-list-pager flex items-center justify-between gap-2 text-sm text-muted-foreground">
            <Button
              variant="outline"
              size="sm"
              onClick={onPrev}
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
              onClick={onNext}
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

export default UserList;
