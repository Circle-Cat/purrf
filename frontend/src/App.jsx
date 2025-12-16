import {
  BrowserRouter as Router,
  Routes,
  Route,
  Navigate,
} from "react-router-dom";
import "@/App.css";
import Header from "@/components/layout/Header";
import Sidebar from "@/components/layout/Sidebar";
import ProtectedRoute from "@/components/common/ProtectedRoute";
import Dashboard from "@/pages/Dashboard";
import DataSearch from "@/pages/DataSearch";
import Profile from "@/pages/Profile";
import AccessDenied from "@/pages/AccessDenied";
import PersonalDashboard from "@/pages/PersonalDashboard";
import { AuthProvider } from "@/context/auth";
import { USER_ROLES } from "@/constants/UserRoles";
import { ROUTE_PATHS } from "@/constants/RoutePaths";

function App() {
  return (
    <AuthProvider>
      <Router>
        <div className="app-container">
          <Header />
          <div className="app-body">
            <Sidebar />
            <main className="main-content">
              <Routes>
                <Route
                  path={ROUTE_PATHS.DASHBOARD}
                  element={
                    <ProtectedRoute
                      requiredRoles={[USER_ROLES.ADMIN, USER_ROLES.CC_INTERNAL]}
                    >
                      <Dashboard />
                    </ProtectedRoute>
                  }
                />
                <Route
                  path={ROUTE_PATHS.DATASEARCH}
                  element={
                    <ProtectedRoute requiredRoles={[USER_ROLES.ADMIN]}>
                      <DataSearch />
                    </ProtectedRoute>
                  }
                />
                <Route
                  path={ROUTE_PATHS.PROFILE}
                  element={
                    <ProtectedRoute requiredRoles={[USER_ROLES.MENTORSHIP]}>
                      <Profile />
                    </ProtectedRoute>
                  }
                />
                <Route
                  path={ROUTE_PATHS.PERSONAL_DASHBOARD}
                  element={
                    <ProtectedRoute requiredRoles={[USER_ROLES.MENTORSHIP]}>
                      <PersonalDashboard />
                    </ProtectedRoute>
                  }
                />
                <Route
                  path={ROUTE_PATHS.ACCESS_DENIED}
                  element={<AccessDenied />}
                />
                <Route
                  path={ROUTE_PATHS.ROOT}
                  element={
                    <ProtectedRoute requiredRoles={[USER_ROLES.MENTORSHIP]}>
                      <Navigate to={ROUTE_PATHS.PERSONAL_DASHBOARD} replace />
                    </ProtectedRoute>
                  }
                />
              </Routes>
            </main>
          </div>
        </div>
      </Router>
    </AuthProvider>
  );
}
export default App;
