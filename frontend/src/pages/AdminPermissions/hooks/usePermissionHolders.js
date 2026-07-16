import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { getPermissionHolders } from "@/api/adminPermissionsApi";
import { useRequestGuard } from "@/hooks/useRequestGuard";

/**
 * Reverse lookup: choose a permission, see who holds it. The permission and
 * include-revoked inputs are staged as draft state and only take effect when
 * submitSearch() runs (the Search button) — nothing is fetched on mount or on
 * input change.
 */
export const usePermissionHolders = () => {
  // Draft inputs — applied only when submitSearch() is called.
  const [permissionName, setPermissionName] = useState("");
  const [includeRevoked, setIncludeRevoked] = useState(false);

  // Committed query: null until the user runs a search.
  const [query, setQuery] = useState(null);
  const [grants, setGrants] = useState([]);
  const [loading, setLoading] = useState(false);
  const { begin, isCurrent } = useRequestGuard();

  const fetchHolders = useCallback(async () => {
    if (!query || !query.permissionName) {
      setGrants([]);
      return;
    }
    const seq = begin();
    setLoading(true);
    try {
      const { data } = await getPermissionHolders(query.permissionName, {
        includeRevoked: query.includeRevoked,
      });
      if (!isCurrent(seq)) return;
      setGrants(data.grants ?? []);
    } catch (err) {
      if (!isCurrent(seq)) return;
      toast.error(err?.response?.data?.message ?? "Failed to load holders");
      setGrants([]);
    } finally {
      if (isCurrent(seq)) setLoading(false);
    }
  }, [query, begin, isCurrent]);

  // Refetch only when the committed query changes — never on mount.
  useEffect(() => {
    fetchHolders();
  }, [fetchHolders]);

  /** Commit the current draft inputs as the active query and load holders. */
  const submitSearch = () => {
    setQuery({ permissionName, includeRevoked });
  };

  return {
    permissionName,
    setPermissionName,
    includeRevoked,
    setIncludeRevoked,
    submitSearch,
    hasSearched: query !== null,
    grants,
    loading,
  };
};
