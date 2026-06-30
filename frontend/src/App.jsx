import { useState } from "react";
import {
  BrowserRouter as Router,
  Routes,
  Route,
  Navigate,
} from "react-router-dom";
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
import AdminPermissions from "@/pages/AdminPermissions";
import Postings from "@/pages/Recruiting/Postings";
import PostingEditor from "@/pages/Recruiting/postings/PostingEditor";
import MyReviews from "@/pages/Recruiting/MyReviews";
import { AuthProvider } from "@/context/auth";
import { FlagsProvider, LDIdentifier } from "@/context/flags";
import { PERMISSIONS } from "@/constants/Permissions";
import { ROUTE_PATHS } from "@/constants/RoutePaths";
import { Toaster } from "@/components/ui/sonner";

function App() {
  const deployEnv = import.meta.env.VITE_DEPLOY_ENV;

  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

  const showEnvBanner = isBannerEnv(deployEnv);
  return (
    <FlagsProvider>
      <AuthProvider>
        <LDIdentifier />
        <Router>
          <div
            className="group flex flex-col"
            data-env-banner={showEnvBanner ? "true" : "false"}
            data-collapsed={sidebarCollapsed ? "true" : "false"}
          >
            <Header
              onToggleSidebar={() => setSidebarCollapsed((prev) => !prev)}
              sidebarCollapsed={sidebarCollapsed}
            />
            {showEnvBanner && <EnvironmentBanner env={deployEnv} />}
            <div className="flex flex-1">
              <Sidebar />
              <main className="ml-64 mt-16 flex min-h-[calc(100vh-64px)] flex-1 flex-col overflow-y-auto p-[30px] transition-[margin] duration-200 group-data-[collapsed=true]:ml-0 group-data-[env-banner=true]:mt-[104px] group-data-[env-banner=true]:min-h-[calc(100vh-104px)]">
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
                      path={ROUTE_PATHS.ADMIN_USERS}
                      element={
                        <ProtectedRoute
                          requiredPermissions={[PERMISSIONS.PERMISSION_MANAGE]}
                        >
                          <AdminPermissions />
                        </ProtectedRoute>
                      }
                    />
                    <Route
                      path={ROUTE_PATHS.RECRUITING_POSTINGS}
                      element={
                        <ProtectedRoute
                          requiredPermissions={[
                            PERMISSIONS.RECRUITING_JOB_WRITE,
                          ]}
                        >
                          <Postings />
                        </ProtectedRoute>
                      }
                    />
                    <Route
                      path={ROUTE_PATHS.RECRUITING_POSTING_NEW}
                      element={
                        <ProtectedRoute
                          requiredPermissions={[
                            PERMISSIONS.RECRUITING_JOB_WRITE,
                          ]}
                        >
                          <PostingEditor />
                        </ProtectedRoute>
                      }
                    />
                    <Route
                      path="/recruiting/postings/:id/edit"
                      element={
                        <ProtectedRoute
                          requiredPermissions={[
                            PERMISSIONS.RECRUITING_JOB_WRITE,
                          ]}
                        >
                          <PostingEditor />
                        </ProtectedRoute>
                      }
                    />
                    <Route
                      path={ROUTE_PATHS.RECRUITING_REVIEWS}
                      element={
                        <ProtectedRoute
                          requiredPermissions={[
                            PERMISSIONS.RECRUITING_JOB_APPROVE,
                          ]}
                        >
                          <MyReviews />
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
