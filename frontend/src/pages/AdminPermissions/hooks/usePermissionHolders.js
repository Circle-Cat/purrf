import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { getPermissionHolders } from "@/api/adminPermissionsApi";

/**
 * Reverse lookup: choose a permission, see who holds it. No request fires until
 * a permission name is chosen (the path requires it). include-revoked is an
 * optional server-side filter.
 */
export const usePermissionHolders = () => {
  const [permissionName, setPermissionName] = useState("");
  const [includeRevoked, setIncludeRevoked] = useState(false);
  const [grants, setGrants] = useState([]);
  const [loading, setLoading] = useState(false);

  const fetchHolders = useCallback(async () => {
    if (!permissionName) {
      setGrants([]);
      return;
    }
    setLoading(true);
    try {
      const { data } = await getPermissionHolders(permissionName, {
        includeRevoked,
      });
      setGrants(data.grants ?? []);
    } catch (err) {
      toast.error(err?.response?.data?.message ?? "Failed to load holders");
      setGrants([]);
    } finally {
      setLoading(false);
    }
  }, [permissionName, includeRevoked]);

  useEffect(() => {
    fetchHolders();
  }, [fetchHolders]);

  return {
    permissionName,
    setPermissionName,
    includeRevoked,
    setIncludeRevoked,
    grants,
    loading,
  };
};
