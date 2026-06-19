import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { getAuditLog } from "@/api/adminPermissionsApi";

const LIMIT = 50;

/** Empty string filters are sent as undefined (omitted query params). */
const clean = (v) => (v === "" || v == null ? undefined : v);

/**
 * Global permission-change audit feed with user/permission/action filters and
 * offset pagination.
 */
export const useAuditLog = () => {
  const [entries, setEntries] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [filters, setFilters] = useState({
    userId: "",
    permissionName: "",
    action: "",
  });
  const [offset, setOffset] = useState(0);

  const fetchAudit = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await getAuditLog({
        userId: clean(filters.userId),
        permissionName: clean(filters.permissionName),
        action: clean(filters.action),
        limit: LIMIT,
        offset,
      });
      setEntries(data.entries ?? []);
      setTotal(data.total ?? 0);
    } catch (err) {
      toast.error(err?.response?.data?.message ?? "Failed to load audit log");
      setEntries([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  }, [filters, offset]);

  useEffect(() => {
    fetchAudit();
  }, [fetchAudit]);

  const setFilter = (key, value) => {
    setFilters((f) => ({ ...f, [key]: value }));
    setOffset(0);
  };
  const nextPage = () => {
    if (offset + LIMIT < total) setOffset((o) => o + LIMIT);
  };
  const prevPage = () => setOffset((o) => Math.max(0, o - LIMIT));

  return {
    entries,
    total,
    loading,
    filters,
    setFilter,
    offset,
    limit: LIMIT,
    nextPage,
    prevPage,
  };
};
