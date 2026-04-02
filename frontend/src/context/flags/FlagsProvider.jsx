import { useState, useContext, useEffect } from "react";
import { useLDClient } from "launchdarkly-react-client-sdk";
import { useAuth } from "@/context/auth";
import { FlagsContext } from "./FlagsContext";
import { ldReactContext } from "./ldReactContext";

/**
 * Provides feature flag state to the component tree.
 * Wrap your app with this provider so that {@link useFeatureFlags} works anywhere.
 * Must be an ancestor of {@link LDIdentifier}.
 */
export function FlagsProvider({ children }) {
  const [flags, setFlags] = useState({});

  return (
    <FlagsContext.Provider value={{ flags, setFlags }}>
      {children}
    </FlagsContext.Provider>
  );
}

/**
 * Identifies the authenticated user with LaunchDarkly and syncs flag values into
 * {@link FlagsContext}.
 *
 * Renders nothing. Must be placed inside both {@link FlagsProvider} and `AuthProvider`
 * so it can access both `setFlags` and the authenticated user.
 *
 * Uses `ldReactContext` explicitly so that `useLDClient` reads from the same context
 * instance that `withLDProvider` writes to, regardless of bundle chunk boundaries.
 */
export function LDIdentifier() {
  const ldClient = useLDClient(ldReactContext);
  const { user, roles } = useAuth();
  const { setFlags } = useContext(FlagsContext);

  useEffect(() => {
    if (!ldClient || !user) return;

    ldClient
      .identify({
        kind: "user",
        key: user.sub,
        email: user.email,
        roles: roles ?? [],
      })
      .then(() => {
        setFlags(ldClient.allFlags());
      });

    const handleChange = () => setFlags(ldClient.allFlags());
    ldClient.on("change", handleChange);
    return () => ldClient.off("change", handleChange);
  }, [ldClient, user]);
}
