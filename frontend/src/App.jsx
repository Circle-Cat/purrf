import { BrowserRouter as Router, Routes, Route } from "react-router-dom";
import "@/App.css";
import Header from "@/components/layout/Header";
import Sidebar from "@/components/layout/Sidebar";
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
          <Sidebar />
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
