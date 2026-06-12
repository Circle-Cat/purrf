import { useState, useEffect, useMemo, useCallback } from "react";
import { getUserRoles } from "@/api/rolesApi";
import { AuthContext } from "./AuthContext";

/**
 * Authentication Provider Component.
 *
 * Fetches the current user's roles and verification status from the API and
 * provides them to child components. Exposes `refreshAuth` so flows like the
 * email hard wall can re-pull state (e.g. after a successful OTP) without a
 * full page reload.
 *
 * @component
 * @param {Object} props - Component props
 * @param {React.ReactNode} props.children - Components that need access to authentication data
 */
export const AuthProvider = ({ children }) => {
  const [roles, setRoles] = useState([]);
  const [user, setUser] = useState(null);
  const [hasVerifiedEmail, setHasVerifiedEmail] = useState(false);
  const [loading, setLoading] = useState(true);

  /**
   * Fetches authentication state (roles, identity, verified-email flag).
   * Reusable so callers can refresh after state-changing actions.
   */
  const loadAuth = useCallback(async () => {
    try {
      const { data } = await getUserRoles();
      setRoles(data.roles || []);
      setUser({ sub: data.sub, email: data.email });
      setHasVerifiedEmail(Boolean(data.has_verified_email));
    } catch (error) {
      console.error("Auth initialization failed", error);
      setRoles([]);
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
    () => ({ roles, user, hasVerifiedEmail, loading, refreshAuth: loadAuth }),
    [roles, user, hasVerifiedEmail, loading, loadAuth],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};
