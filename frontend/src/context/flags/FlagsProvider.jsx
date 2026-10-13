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
  const [ready, setReady] = useState(false);

  return (
    <FlagsContext.Provider value={{ flags, setFlags, ready, setReady }}>
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
 * Marks the context `ready` once identify settles either way, so pages that redirect
 * on a flag being off can tell "off" apart from "not answered yet".
 *
 * Uses `ldReactContext` explicitly so that `useLDClient` reads from the same context
 * instance that `withLDProvider` writes to, regardless of bundle chunk boundaries.
 */
export function LDIdentifier() {
  const ldClient = useLDClient(ldReactContext);
  const { user } = useAuth();
  const { setFlags, setReady } = useContext(FlagsContext);

  useEffect(() => {
    if (!ldClient || !user) return;

    ldClient
      .identify({
        kind: "user",
        key: user.sub,
        userId: user.userId,
        email: user.email,
        identity_type: user.identityType,
      })
      .then(() => {
        setFlags(ldClient.allFlags());
      })
      .catch((error) => {
        // Flags stay empty, so everything gated reads as off.
        console.error("LaunchDarkly identify failed", error);
      })
      .finally(() => {
        setReady(true);
      });

    const handleChange = () => setFlags(ldClient.allFlags());
    ldClient.on("change", handleChange);
    return () => ldClient.off("change", handleChange);
  }, [ldClient, user]);
}
