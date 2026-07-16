import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { getAuditLog } from "@/api/adminPermissionsApi";
import { useRequestGuard } from "@/hooks/useRequestGuard";

const LIMIT = 50;

/** Empty string filters are sent as undefined (omitted query params). */
const clean = (v) => (v === "" || v == null ? undefined : v);

/**
 * Global permission-change audit feed. Filter inputs are staged as draft state
 * and only take effect when submitSearch() runs (the Search button) — nothing
 * is fetched on mount. Pagination applies immediately to the committed filters.
 */
export const useAuditLog = () => {
  const [entries, setEntries] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);

  // Draft filters — applied only when submitSearch() is called.
  const [filters, setFilters] = useState({
    userId: "",
    permissionName: "",
    action: "",
  });

  // Committed filters: null until the user runs a search.
  const [query, setQuery] = useState(null);
  const [offset, setOffset] = useState(0);
  const { begin, isCurrent } = useRequestGuard();

  const fetchAudit = useCallback(async () => {
    if (!query) return;
    const seq = begin();
    setLoading(true);
    try {
      const { data } = await getAuditLog({
        userId: clean(query.userId),
        permissionName: clean(query.permissionName),
        action: clean(query.action),
        limit: LIMIT,
        offset,
      });
      if (!isCurrent(seq)) return;
      setEntries(data.entries ?? []);
      setTotal(data.total ?? 0);
    } catch (err) {
      if (!isCurrent(seq)) return;
      toast.error(err?.response?.data?.message ?? "Failed to load audit log");
      setEntries([]);
      setTotal(0);
    } finally {
      if (isCurrent(seq)) setLoading(false);
    }
  }, [query, offset, begin, isCurrent]);

  // Refetch when the committed filters or page change — never on mount.
  useEffect(() => {
    fetchAudit();
  }, [fetchAudit]);

  const setFilter = (key, value) => {
    setFilters((f) => ({ ...f, [key]: value }));
  };

  /** Commit the current draft filters as the active query and load page 1. */
  const submitSearch = () => {
    setOffset(0);
    setQuery({ ...filters });
  };

  const nextPage = () => {
    if (offset + LIMIT < total) setOffset((o) => o + LIMIT);
  };
  const prevPage = () => setOffset((o) => Math.max(0, o - LIMIT));

  return {
    entries,
    total,
    loading,
    hasSearched: query !== null,
    filters,
    setFilter,
    submitSearch,
    offset,
    limit: LIMIT,
    nextPage,
    prevPage,
  };
};
