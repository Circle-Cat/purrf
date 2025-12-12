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
 *   loading: boolean
 * }} The current authentication state containing user roles and loading status.
 *
 * @example
 * const { roles, loading } = useAuth();
 */
export const useAuth = () => {
  return useContext(AuthContext);
};
