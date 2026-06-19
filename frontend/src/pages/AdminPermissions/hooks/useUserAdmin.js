import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import {
  getUsers,
  setSuperAdmin,
  revokeSuperAdmin,
} from "@/api/adminPermissionsApi";

const LIMIT = 20;
const DEBOUNCE_MS = 300;

/**
 * Owns the admin user list: debounced search, offset pagination, sort/filter
 * state, the selected user, and the super-admin mutations (which change
 * AdminUser.isSuperAdmin and therefore belong with the list, not with the
 * per-user permission hook).
 */
export const useUserAdmin = () => {
  const [users, setUsers] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [offset, setOffset] = useState(0);
  const [selectedUser, setSelectedUser] = useState(null);

  // Sort state
  const [sortBy, setSortBy] = useState(null);
  const [order, setOrder] = useState("asc");

  // Filter state
  const [isSuperAdmin, setIsSuperAdmin] = useState(false);
  const [userType, setUserType] = useState("");

  // Debounce the search box; reset to the first page when the term changes.
  useEffect(() => {
    const id = setTimeout(() => {
      setDebouncedSearch(search);
      setOffset(0);
    }, DEBOUNCE_MS);
    return () => clearTimeout(id);
  }, [search]);

  // Reset page when sort or filters change.
  useEffect(() => {
    setOffset(0);
  }, [sortBy, order, isSuperAdmin, userType]);

  const fetchUsers = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await getUsers({
        search: debouncedSearch,
        limit: LIMIT,
        offset,
        sortBy: sortBy ?? undefined,
        order,
        isSuperAdmin: isSuperAdmin || undefined,
        userType: userType || undefined,
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
  }, [debouncedSearch, offset, sortBy, order, isSuperAdmin, userType]);

  useEffect(() => {
    fetchUsers();
  }, [fetchUsers]);

  const nextPage = () => {
    if (offset + LIMIT < total) setOffset((o) => o + LIMIT);
  };
  const prevPage = () => setOffset((o) => Math.max(0, o - LIMIT));

  const selectUser = (user) => setSelectedUser(user);

  /**
   * Toggle sort: if the given backend field is already active, flip the order;
   * otherwise activate it with "asc".
   * @param {string} field - Backend sort_by field name (e.g. "last_name").
   */
  const toggleSort = (field) => {
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
    search,
    setSearch,
    offset,
    limit: LIMIT,
    nextPage,
    prevPage,
    selectedUser,
    selectUser,
    makeSuperAdmin,
    revokeSuperAdminFor,
    // Sort
    sortBy,
    order,
    toggleSort,
    // Filters
    isSuperAdmin,
    setIsSuperAdmin,
    userType,
    setUserType,
  };
};
