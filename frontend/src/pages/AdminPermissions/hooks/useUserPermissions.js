import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import {
  getUserPermissions,
  grantPermissions,
  revokePermissions,
} from "@/api/adminPermissionsApi";

/**
 * Owns the selected user's active permissions + history and the grant/revoke
 * save-diff. After any save attempt it refetches the view so the UI reflects
 * server truth even on partial failure.
 *
 * @param {number|null} userId
 */
export const useUserPermissions = (userId) => {
  const [active, setActive] = useState([]);
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(false);

  const fetchView = useCallback(async () => {
    if (userId == null) return;
    setLoading(true);
    try {
      const { data } = await getUserPermissions(userId);
      setActive(data.active ?? []);
      setHistory(data.history ?? []);
    } catch (err) {
      toast.error(err?.response?.data?.message ?? "Failed to load permissions");
    } finally {
      setLoading(false);
    }
  }, [userId]);

  useEffect(() => {
    if (userId == null) {
      setActive([]);
      setHistory([]);
      return;
    }
    fetchView();
  }, [userId, fetchView]);

  const saveDiff = useCallback(
    async (checked) => {
      if (userId == null) return;
      const checkedSet = new Set(checked);
      const activeSet = new Set(active);
      const added = checked.filter((p) => !activeSet.has(p));
      const removed = active.filter((p) => !checkedSet.has(p));
      if (added.length === 0 && removed.length === 0) return;

      // Grant and revoke are independent backend calls. Attempt BOTH even if
      // one throws — otherwise a failed grant would silently skip an intended
      // revoke (a security-relevant action the admin believes they made).
      const failures = [];
      if (added.length) {
        try {
          await grantPermissions(userId, added);
        } catch (err) {
          failures.push({ op: "grant", err });
        }
      }
      if (removed.length) {
        try {
          await revokePermissions(userId, removed);
        } catch (err) {
          failures.push({ op: "revoke", err });
        }
      }

      if (failures.length === 0) {
        toast.success("Permissions updated");
      } else {
        // Prefer a specific backend reason; otherwise name which half failed so
        // the admin knows what did and did not apply.
        const serverMessage = failures.find(
          (f) => f.err?.response?.data?.message,
        )?.err.response.data.message;
        const failedOps = failures.map((f) => f.op).join(" and ");
        toast.error(serverMessage ?? `Failed to ${failedOps} permissions`);
      }

      await fetchView();
    },
    [userId, active, fetchView],
  );

  return { active, history, loading, saveDiff };
};
