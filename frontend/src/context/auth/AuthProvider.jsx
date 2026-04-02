import { useState, useEffect, useMemo } from "react";
import { getUserRoles } from "@/api/rolesApi";
import { AuthContext } from "./AuthContext";

/**
 * Authentication Provider Component.
 *
 * Fetches user roles from the API and provides authentication data to child components.
 * Automatically initializes roles when the component mounts.
 *
 * @component
 * @param {Object} props - Component props
 * @param {React.ReactNode} props.children - Components that need access to authentication data
 */
export const AuthProvider = ({ children }) => {
  const [roles, setRoles] = useState([]);
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    /**
     * Initializes authentication state.
     * Asynchronously fetches user roles and handles success/loading states.
     */
    const initAuth = async () => {
      try {
        const { data } = await getUserRoles();
        setRoles(data.roles || []);
        setUser({ sub: data.sub, email: data.email });
      } catch (error) {
        console.error("Auth initialization failed", error);
        setRoles([]);
      } finally {
        setLoading(false);
      }
    };

    initAuth();
  }, []);

  /**
   * Memoizes the context value to prevent unnecessary re-renders.
   * The value is only recalculated when 'roles', 'user', or 'loading' state changes.
   */
  const value = useMemo(
    () => ({ roles, user, loading }),
    [roles, user, loading],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};
