import {
  BrowserRouter as Router,
  Routes,
  Route,
  Navigate,
} from "react-router-dom";
import "@/App.css";
import Header from "@/components/layout/Header";
import EnvironmentBanner from "@/components/layout/EnvironmentBanner";
import { isBannerEnv } from "@/utils/deployEnv";
import Sidebar from "@/components/layout/Sidebar";
import ProtectedRoute from "@/components/common/ProtectedRoute";
import HardWallGate from "@/components/common/HardWallGate";
import Dashboard from "@/pages/Dashboard";
import DataSearch from "@/pages/DataSearch";
import Profile from "@/pages/Profile";
import AccessDenied from "@/pages/AccessDenied";
import PersonalDashboard from "@/pages/PersonalDashboard";
import MentorshipManagement from "@/pages/MentorshipManagement";
import VerifyRequired from "@/pages/VerifyRequired";
import SignInSecurity from "@/pages/SignInSecurity";
import { AuthProvider } from "@/context/auth";
import { FlagsProvider, LDIdentifier } from "@/context/flags";
import { PERMISSIONS } from "@/constants/Permissions";
import { ROUTE_PATHS } from "@/constants/RoutePaths";
import { Toaster } from "@/components/ui/sonner";

function App() {
  const deployEnv = import.meta.env.VITE_DEPLOY_ENV;

  const showEnvBanner = isBannerEnv(deployEnv);
  const containerClassName = `app-container legacy-styles${
    showEnvBanner ? " has-env-banner" : ""
  }`;
  return (
    <FlagsProvider>
      <AuthProvider>
        <LDIdentifier />
        <Router>
          <div className={containerClassName}>
            <Header />
            {showEnvBanner && <EnvironmentBanner env={deployEnv} />}
            <div className="app-body">
              <Sidebar />
              <main className="main-content">
                <HardWallGate>
                  <Routes>
                    <Route
                      path={ROUTE_PATHS.VERIFY_REQUIRED}
                      element={<VerifyRequired />}
                    />
                    <Route
                      path={ROUTE_PATHS.DASHBOARD}
                      element={
                        <ProtectedRoute
                          requiredPermissions={[
                            PERMISSIONS.DASHBOARD_ACTIVITY_SUMMARY_READ,
                          ]}
                        >
                          <Dashboard />
                        </ProtectedRoute>
                      }
                    />
                    <Route
                      path={ROUTE_PATHS.DATASEARCH}
                      element={
                        <ProtectedRoute
                          requiredPermissions={[
                            PERMISSIONS.INTERNAL_ACTIVITY_READ,
                          ]}
                        >
                          <DataSearch />
                        </ProtectedRoute>
                      }
                    />
                    <Route path={ROUTE_PATHS.PROFILE} element={<Profile />} />
                    <Route
                      path={ROUTE_PATHS.SIGN_IN_SECURITY}
                      element={<SignInSecurity />}
                    />
                    <Route
                      path={ROUTE_PATHS.PERSONAL_DASHBOARD}
                      element={<PersonalDashboard />}
                    />
                    <Route
                      path={ROUTE_PATHS.MENTORSHIP_MANAGEMENT}
                      element={
                        <ProtectedRoute
                          requiredPermissions={[
                            PERMISSIONS.MENTORSHIP_MANAGEMENT_READ,
                          ]}
                        >
                          <MentorshipManagement />
                        </ProtectedRoute>
                      }
                    />
                    <Route
                      path={ROUTE_PATHS.ACCESS_DENIED}
                      element={<AccessDenied />}
                    />
                    <Route
                      path={ROUTE_PATHS.ROOT}
                      element={<Navigate to={ROUTE_PATHS.PROFILE} replace />}
                    />
                  </Routes>
                </HardWallGate>
              </main>
            </div>
          </div>
          <Toaster richColors position="top-center" closeButton />
        </Router>
      </AuthProvider>
    </FlagsProvider>
  );
}

export default App;
