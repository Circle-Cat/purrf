import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { withLDProvider } from "launchdarkly-react-client-sdk";
import { ldReactContext } from "@/context/flags";
import "./index.css";
import App from "./App.jsx";

// Pass ldReactContext explicitly so withLDProvider and useLDClient share the same
// context instance across module chunks in the production bundle.
const AppWithLD = withLDProvider({
  clientSideID: import.meta.env.VITE_LAUNCHDARKLY_CLIENT_ID,
  reactOptions: { reactContext: ldReactContext },
})(App);

createRoot(document.getElementById("root")).render(
  <StrictMode>
    <AppWithLD />
  </StrictMode>,
);
