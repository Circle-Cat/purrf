import { Navigate } from "react-router-dom";
import { useAuth } from "@/context/auth";
import { ROUTE_PATHS } from "@/constants/RoutePaths";

/**
 * A wrapper component that restricts route access based on user roles.
 *
 * It retrieves the current user's roles from the `useAuth` hook and compares them
 * against the `requiredRoles` prop.
 *
 * - Renders `null` while authentication state is loading.
 * - Redirects to "/access-denied" if the user lacks the necessary permissions.
 * - Renders the `children` if the user has at least one matching role.
 *
 * @component
 * @param {Object} props - The component props.
 * @param {React.ReactNode} props.children - The child components to render upon successful authorization.
 * @param {string[]} props.requiredRoles - An array of role strings that are allowed to access this route.
 * @returns {JSX.Element|null} The children, a Navigate component, or null.
 *
 * @example
 * <ProtectedRoute requiredRoles={[USER_ROLES.MENTORSHIP]}>
 *   <PersonalDashboard />
 * </ProtectedRoute>
 */
const ProtectedRoute = ({ children, requiredRoles }) => {
  const { roles, loading } = useAuth();
  if (loading) return null;

  const hasPermission = roles.some((role) => requiredRoles.includes(role));
  if (!hasPermission) {
    return <Navigate to={ROUTE_PATHS.ACCESS_DENIED} replace />;
  }

  return children;
};

export default ProtectedRoute;
