import { useMemo, useState } from "react";
import { Search } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import StateChips from "@/pages/UserAdminPrototype/StateChips";
import { fullName, statesOf } from "@/pages/UserAdminPrototype/accountState";

const PAGE_SIZE = 8;

/**
 * Free-text search, matching what the endpoint is specified to cover: name,
 * any address on the account, the numeric id, and — only here, never on the
 * permission page — the block reason. Searching by reason is behaviour the
 * deleted recruiting blacklist page had, and it must not be lost.
 */
const matchesSearch = (user, term) => {
  if (!term) return true;
  const needle = term.toLowerCase();
  return (
    fullName(user).toLowerCase().includes(needle) ||
    String(user.userId).includes(needle) ||
    user.emails.some((e) => e.address.toLowerCase().includes(needle)) ||
    (user.blockedReason ?? "").toLowerCase().includes(needle)
  );
};

const matchesStatus = (user, status, pending) => {
  if (status === "all") return true;
  if (status === "blocked") return user.isBlocked;
  if (status === "deactivated") return !user.isActive;
  if (status === "requested") return pending;
  return user.isActive && !user.isBlocked;
};

/**
 * AccountsPage
 *
 * The operator's list. One search over the whole population — the only such
 * search in the product — with the account-state filters that make it useful
 * for triage.
 *
 * @param {{users: object[], requests: object[], onOpen: Function,
 *   statusFilter: string, onStatusFilter: Function}} props
 * @returns {JSX.Element}
 */
const AccountsPage = ({
  users,
  requests,
  onOpen,
  statusFilter,
  onStatusFilter,
}) => {
  const [term, setTerm] = useState("");
  const [type, setType] = useState("all");
  const [page, setPage] = useState(0);

  const pendingIds = useMemo(
    () =>
      new Set(
        requests
          .filter((r) => r.status === "pending")
          .map((r) => r.targetUserId),
      ),
    [requests],
  );

  const rows = useMemo(
    () =>
      users.filter(
        (u) =>
          matchesSearch(u, term) &&
          matchesStatus(u, statusFilter, pendingIds.has(u.userId)) &&
          (type === "all" || u.userType === type),
      ),
    [users, term, statusFilter, type, pendingIds],
  );

  const pageCount = Math.max(1, Math.ceil(rows.length / PAGE_SIZE));
  const current = Math.min(page, pageCount - 1);
  const visible = rows.slice(
    current * PAGE_SIZE,
    current * PAGE_SIZE + PAGE_SIZE,
  );
  const pendingCount = pendingIds.size;

  const reset = (fn) => (value) => {
    setPage(0);
    fn(value);
  };

  return (
    <div className="space-y-4">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold text-slate-900">Accounts</h1>
          <p className="mt-0.5 text-sm text-slate-600">
            Who someone is, what state their account is in, and how they sign
            in.
          </p>
        </div>
        <Badge
          variant="outline"
          className="shrink-0 border-slate-300 text-slate-600"
        >
          {rows.length} of {users.length}
        </Badge>
      </div>

      {pendingCount > 0 && statusFilter !== "requested" && (
        <div className="flex items-center justify-between gap-3 rounded-md border border-amber-300 bg-amber-50 px-3 py-2">
          <p className="text-sm text-amber-900">
            {pendingCount} block request{pendingCount === 1 ? "" : "s"} awaiting
            a decision.
          </p>
          <Button
            variant="outline"
            size="sm"
            className="border-amber-400 bg-white"
            onClick={() => onStatusFilter("requested")}
          >
            Show them
          </Button>
        </div>
      )}

      <div className="flex flex-wrap items-center gap-2">
        <div className="relative min-w-64 flex-1">
          <Search
            size={14}
            className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400"
          />
          <Input
            className="pl-8"
            placeholder="Name, email, user ID, or block reason"
            value={term}
            onChange={(e) => reset(setTerm)(e.target.value)}
          />
        </div>
        <Select value={type} onValueChange={reset(setType)}>
          <SelectTrigger className="w-36">
            <SelectValue placeholder="Type" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Any type</SelectItem>
            <SelectItem value="internal">Internal</SelectItem>
            <SelectItem value="external">External</SelectItem>
          </SelectContent>
        </Select>
        <Select value={statusFilter} onValueChange={reset(onStatusFilter)}>
          <SelectTrigger className="w-44">
            <SelectValue placeholder="Status" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Any status</SelectItem>
            <SelectItem value="active">Active</SelectItem>
            <SelectItem value="blocked">Blocked</SelectItem>
            <SelectItem value="deactivated">Deactivated</SelectItem>
            <SelectItem value="requested">Block requested</SelectItem>
          </SelectContent>
        </Select>
      </div>

      <div className="overflow-x-auto rounded-md border border-slate-200">
        <Table>
          <TableHeader>
            <TableRow className="bg-slate-50">
              <TableHead className="w-20">ID</TableHead>
              <TableHead>Name</TableHead>
              <TableHead>Contact email</TableHead>
              <TableHead className="w-24">Type</TableHead>
              <TableHead className="w-44">Status</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {visible.map((user) => (
              <TableRow
                key={user.userId}
                className="cursor-pointer"
                onClick={() => onOpen(user.userId)}
              >
                <TableCell className="tabular-nums text-slate-500">
                  {user.userId}
                </TableCell>
                <TableCell className="font-medium text-slate-900">
                  {fullName(user)}
                  {user.isSuperAdmin && (
                    <span className="ml-1.5 text-amber-600" title="Super admin">
                      ★
                    </span>
                  )}
                </TableCell>
                <TableCell className="text-slate-600">
                  {user.contactEmail}
                </TableCell>
                <TableCell className="text-slate-600">
                  {user.userType === "internal" ? "Internal" : "External"}
                </TableCell>
                <TableCell>
                  <StateChips
                    states={statesOf(user, pendingIds.has(user.userId))}
                  />
                </TableCell>
              </TableRow>
            ))}
            {visible.length === 0 && (
              <TableRow>
                <TableCell
                  colSpan={5}
                  className="py-10 text-center text-sm text-slate-500"
                >
                  No account matches these filters.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>

      <div className="flex items-center justify-end gap-2 text-sm text-slate-600">
        <Button
          variant="outline"
          size="sm"
          disabled={current === 0}
          onClick={() => setPage(current - 1)}
        >
          Previous
        </Button>
        <span className="tabular-nums">
          {current + 1} / {pageCount}
        </span>
        <Button
          variant="outline"
          size="sm"
          disabled={current >= pageCount - 1}
          onClick={() => setPage(current + 1)}
        >
          Next
        </Button>
      </div>
    </div>
  );
};

export default AccountsPage;
