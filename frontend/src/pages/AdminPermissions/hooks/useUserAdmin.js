import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import {
  getUsers,
  setSuperAdmin,
  revokeSuperAdmin,
} from "@/api/adminPermissionsApi";

const LIMIT = 20;

/**
 * Owns the admin user list. Search/filter inputs are staged as draft state and
 * only take effect when submitSearch() runs (the Search button) — nothing is
 * fetched on mount. Sorting and pagination apply immediately to the committed
 * query. Also owns the selected user and the super-admin mutations (which
 * change AdminUser.isSuperAdmin and therefore belong with the list).
 */
export const useUserAdmin = () => {
  const [users, setUsers] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [selectedUser, setSelectedUser] = useState(null);

  // Draft search/filter inputs — applied only when submitSearch() is called.
  const [search, setSearch] = useState("");
  const [userId, setUserId] = useState("");
  const [isSuperAdmin, setIsSuperAdmin] = useState(false);
  const [userType, setUserType] = useState("");

  // Committed query: null until the user runs a search. A new object reference
  // is set on every submit so re-submitting the same criteria still refetches.
  const [query, setQuery] = useState(null);
  const [offset, setOffset] = useState(0);

  // Sort state (applies to the committed query).
  const [sortBy, setSortBy] = useState(null);
  const [order, setOrder] = useState("asc");

  const fetchUsers = useCallback(async () => {
    if (!query) return;
    setLoading(true);
    try {
      const { data } = await getUsers({
        search: query.search || undefined,
        userId: query.userId || undefined,
        limit: LIMIT,
        offset,
        sortBy: sortBy ?? undefined,
        order,
        isSuperAdmin: query.isSuperAdmin || undefined,
        userType: query.userType || undefined,
      });
      setUsers(data.users ?? []);
      setTotal(data.total ?? 0);
    } catch (err) {
      toast.error(err?.response?.data?.message ?? "Failed to load users");
      setUsers([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  }, [query, offset, sortBy, order]);

  // Refetch when the committed query, sort, or page changes — never on mount.
  useEffect(() => {
    fetchUsers();
  }, [fetchUsers]);

  /** Commit the current draft inputs as the active query and load page 1. */
  const submitSearch = () => {
    setOffset(0);
    setQuery({ search, userId, isSuperAdmin, userType });
  };

  const nextPage = () => {
    if (offset + LIMIT < total) setOffset((o) => o + LIMIT);
  };
  const prevPage = () => setOffset((o) => Math.max(0, o - LIMIT));

  const selectUser = (user) => setSelectedUser(user);

  /**
   * Toggle sort: if the given backend field is already active, flip the order;
   * otherwise activate it with "asc". Resets to the first page.
   * @param {string} field - Backend sort_by field name (e.g. "last_name").
   */
  const toggleSort = (field) => {
    setOffset(0);
    if (sortBy === field) {
      setOrder((prev) => (prev === "asc" ? "desc" : "asc"));
    } else {
      setSortBy(field);
      setOrder("asc");
    }
  };

  // After a super-admin change, refresh the list and re-sync the selected user
  // from the refreshed AdminUser the endpoint returns.
  const applySuperAdmin = async (fn) => {
    if (!selectedUser) return;
    try {
      const { data } = await fn(selectedUser.userId);
      setSelectedUser(data);
      toast.success("Super-admin updated");
      await fetchUsers();
    } catch (err) {
      toast.error(
        err?.response?.data?.message ?? "Failed to update super-admin",
      );
    }
  };

  const makeSuperAdmin = () => applySuperAdmin(setSuperAdmin);
  const revokeSuperAdminFor = () => applySuperAdmin(revokeSuperAdmin);

  return {
    users,
    total,
    loading,
    hasSearched: query !== null,
    // Draft inputs
    search,
    setSearch,
    userId,
    setUserId,
    isSuperAdmin,
    setIsSuperAdmin,
    userType,
    setUserType,
    submitSearch,
    // Pagination
    offset,
    limit: LIMIT,
    nextPage,
    prevPage,
    // Selection + super-admin mutations
    selectedUser,
    selectUser,
    makeSuperAdmin,
    revokeSuperAdminFor,
    // Sort
    sortBy,
    order,
    toggleSort,
  };
};
