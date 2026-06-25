import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "./index.css";
import ResumeParserDemo from "@/pages/ResumeParserDemo";

// Standalone, backend-free entry for demoing the resume parser. It mounts ONLY
// the demo page — none of App.jsx's auth / feature-flag / layout providers or
// the HardWallGate — so it runs fully offline with no login and no backend.
//
// Dev only: `bazel run //frontend:dev_server`, then open /resume-demo.html.
// Not part of the production build (index.html is the sole Vite input).
createRoot(document.getElementById("root")).render(
  <StrictMode>
    <ResumeParserDemo />
  </StrictMode>,
);
