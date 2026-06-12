import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "@/context/auth";
import { ROUTE_PATHS } from "@/constants/RoutePaths";

/**
 * Root-level guard enforcing the email hard wall.
 *
 * A user with no OTP-confirmed contact email is held at `/verify-required`:
 * any other path is redirected there, so no Purrf page is reachable until they
 * verify (or log out). Once verified, the wall page itself redirects away.
 *
 * Wrap the app's <Routes> with this; the `/verify-required` route must live
 * inside so it can render while the user is still unverified.
 *
 * @component
 * @param {Object} props
 * @param {React.ReactNode} props.children - the route tree to guard.
 */
const HardWallGate = ({ children }) => {
  const { loading, hasVerifiedEmail } = useAuth();
  const location = useLocation();

  if (loading) return null;

  const onWall = location.pathname === ROUTE_PATHS.VERIFY_REQUIRED;

  if (!hasVerifiedEmail && !onWall) {
    return <Navigate to={ROUTE_PATHS.VERIFY_REQUIRED} replace />;
  }
  if (hasVerifiedEmail && onWall) {
    return <Navigate to={ROUTE_PATHS.PROFILE} replace />;
  }

  return children;
};

export default HardWallGate;
