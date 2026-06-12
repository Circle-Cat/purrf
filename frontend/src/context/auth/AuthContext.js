import { createContext, useContext } from "react";

/**
 * Authentication Context.
 * Provides authentication state (e.g., user roles, loading status) to the component tree.
 */
export const AuthContext = createContext(null);

/**
 * Custom Hook to access Authentication Context.
 * A wrapper around useContext to easily retrieve authentication data.
 *
 * @returns {{
 *   roles: string[],
 *   user: { sub: string, email: string } | null,
 *   hasVerifiedEmail: boolean,
 *   loading: boolean,
 *   refreshAuth: () => Promise<void>
 * }} The current authentication state plus a refresher to re-pull it.
 *
 * @example
 * const { roles, loading } = useAuth();
 */
export const useAuth = () => {
  return useContext(AuthContext);
};
