import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { getPermissionHolders } from "@/api/adminPermissionsApi";

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

  const fetchHolders = useCallback(async () => {
    if (!query || !query.permissionName) {
      setGrants([]);
      return;
    }
    setLoading(true);
    try {
      const { data } = await getPermissionHolders(query.permissionName, {
        includeRevoked: query.includeRevoked,
      });
      setGrants(data.grants ?? []);
    } catch (err) {
      toast.error(err?.response?.data?.message ?? "Failed to load holders");
      setGrants([]);
    } finally {
      setLoading(false);
    }
  }, [query]);

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
