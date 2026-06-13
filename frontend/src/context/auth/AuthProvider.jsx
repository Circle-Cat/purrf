import { useState, useEffect, useMemo, useCallback } from "react";
import { getUserPermissions } from "@/api/permissionsApi";
import { AuthContext } from "./AuthContext";

/**
 * Authentication Provider Component.
 *
 * Fetches the current user's permissions and verification status from the API
 * and provides them to child components. Exposes `refreshAuth` so flows like the
 * email hard wall can re-pull state (e.g. after a successful OTP) without a
 * full page reload.
 *
 * @component
 * @param {Object} props - Component props
 * @param {React.ReactNode} props.children - Components that need access to authentication data
 */
export const AuthProvider = ({ children }) => {
  const [permissions, setPermissions] = useState([]);
  const [user, setUser] = useState(null);
  const [isSuperAdmin, setIsSuperAdmin] = useState(false);
  const [hasVerifiedEmail, setHasVerifiedEmail] = useState(false);
  const [loading, setLoading] = useState(true);

  /**
   * Fetches authentication state (permissions, identity, verified-email flag).
   * Reusable so callers can refresh after state-changing actions.
   */
  const loadAuth = useCallback(async () => {
    try {
      const { data } = await getUserPermissions();
      setPermissions(data.permissions || []);
      setUser({
        sub: data.sub,
        userId: data.user_id,
        email: data.email,
        identityType: data.identity_type,
      });
      setIsSuperAdmin(Boolean(data.is_super_admin));
      setHasVerifiedEmail(Boolean(data.has_verified_email));
    } catch (error) {
      console.error("Auth initialization failed", error);
      setPermissions([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadAuth();
  }, [loadAuth]);

  /**
   * Memoizes the context value to prevent unnecessary re-renders.
   */
  const value = useMemo(
    () => ({
      permissions,
      user,
      isSuperAdmin,
      hasVerifiedEmail,
      loading,
      refreshAuth: loadAuth,
    }),
    [permissions, user, isSuperAdmin, hasVerifiedEmail, loading, loadAuth],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};
