import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "./index.css";
import PrototypeSwitcher from "@/PrototypeSwitcher";

// Standalone entry for the static GitHub Pages build of the prototypes. Unlike
// src/main.jsx it deliberately skips the Auth0, LaunchDarkly, and react-router
// providers: the prototypes are self-contained mock data with no backend, so
// mounting them bare keeps the static bundle free of any runtime env vars.
// Built via frontend/vite.config.pages.mjs; see .github/workflows/deploy-pages.yml.
createRoot(document.getElementById("root")).render(
  <StrictMode>
    <PrototypeSwitcher />
  </StrictMode>,
);
