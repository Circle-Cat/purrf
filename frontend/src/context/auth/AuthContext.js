import { createContext, useContext } from "react";

/**
 * Authentication Context.
 * Provides authentication state (e.g., user permissions, loading status) to the component tree.
 */
export const AuthContext = createContext(null);

/**
 * Custom Hook to access Authentication Context.
 * A wrapper around useContext to easily retrieve authentication data.
 *
 * @returns {{
 *   permissions: string[],
 *   user: { sub: string, userId: number, email: string, identityType: string } | null,
 *   isSuperAdmin: boolean,
 *   hasVerifiedEmail: boolean,
 *   accessDenied: boolean,
 *   accessDeniedMessage: string,
 *   authError: boolean,
 *   sessionExpired: boolean,
 *   authRefusalMessage: string | null,
 *   loading: boolean,
 *   refreshAuth: () => Promise<void>
 * }} The current authentication state plus a refresher to re-pull it.
 *   `authError` is true when the auth pull failed for a non-403 reason (401,
 *   network, timeout, 5xx, 400); `sessionExpired` narrows that to a 401.
 *   `authRefusalMessage` narrows it further to a 400 — the backend explicitly
 *   refusing the login (e.g. an unlisted connection) with an actionable
 *   message — and holds that message verbatim; it is null for every other
 *   failure (including a 400 with no message body).
 *
 * @example
 * const { permissions, loading } = useAuth();
 */
export const useAuth = () => {
  return useContext(AuthContext);
};
