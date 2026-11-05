import { Navigate } from "react-router-dom";
import { useAuth } from "@/context/auth";
import { ROUTE_PATHS } from "@/constants/RoutePaths";

/**
 * A wrapper component that restricts route access based on user permissions.
 *
 * It retrieves the current user's permissions from the `useAuth` hook and
 * compares them against the `requiredPermissions` prop.
 *
 * - Renders `null` while authentication state is loading.
 * - Redirects to "/access-denied" if the user lacks the necessary permissions.
 * - Renders the `children` if the user has at least one matching permission.
 *
 * @component
 * @param {Object} props - The component props.
 * @param {React.ReactNode} props.children - The child components to render upon successful authorization.
 * @param {string[]} props.requiredPermissions - An array of permission strings that are allowed to access this route.
 * @returns {JSX.Element|null} The children, a Navigate component, or null.
 *
 * @example
 * <ProtectedRoute requiredPermissions={[PERMISSIONS.INTERNAL_ACTIVITY_READ]}>
 *   <DataSearch />
 * </ProtectedRoute>
 */
const ProtectedRoute = ({ children, requiredPermissions }) => {
  const { permissions, loading } = useAuth();
  if (loading) return null;

  const hasPermission = permissions.some((p) =>
    requiredPermissions.includes(p),
  );
  if (!hasPermission) {
    return <Navigate to={ROUTE_PATHS.ACCESS_DENIED} replace />;
  }

  return children;
};

export default ProtectedRoute;
