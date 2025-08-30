import {
  BrowserRouter as Router,
  Routes,
  Route,
  NavLink,
} from "react-router-dom";
import "@/App.css";
import Header from "@/components/layout/Header";
import Dashboard from "@/pages/Dashboard";

const DataSearch = () => (
  <div style={{ padding: "20px" }}>Data Search Page</div>
);

function App() {
  return (
    <Router>
      <div className="app-container">
        <Header />
        <div className="app-body">
          <div className="sidebar">
            <nav className="sidebar-nav">
              <ul>
                <li>
                  <NavLink
                    to="/dashboard"
                    className={({ isActive }) =>
                      isActive ? "active-link" : ""
                    }
                  >
                    Dashboard
                  </NavLink>
                </li>
                <li>
                  <NavLink
                    to="/datasearch"
                    className={({ isActive }) =>
                      isActive ? "active-link" : ""
                    }
                  >
                    DataSearch
                  </NavLink>
                </li>
              </ul>
            </nav>
          </div>
          <main className="main-content">
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/dashboard" element={<Dashboard />} />
              <Route path="/datasearch" element={<DataSearch />} />
            </Routes>
          </main>
        </div>
      </div>
    </Router>
  );
}

export default App;
