import { useEffect, useState } from "react";
import { toast } from "sonner";
import { getPermissionCatalog } from "@/api/adminPermissionsApi";

/** Fetches the grantable-permission catalog once; shared by all three tabs. */
export const usePermissionCatalog = () => {
  const [catalog, setCatalog] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const { data } = await getPermissionCatalog();
        if (alive) setCatalog(data.permissions ?? []);
      } catch (err) {
        if (alive)
          toast.error(err?.response?.data?.message ?? "Failed to load catalog");
      } finally {
        if (alive) setLoading(false);
      }
    })();
    return () => {
      alive = false;
    };
  }, []);

  return { catalog, loading };
};
