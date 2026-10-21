import { useState, useContext, useEffect, useMemo } from "react";
import { LDProvider, useLDClient } from "launchdarkly-react-client-sdk";
import { useAuth } from "@/context/auth";
import { FlagsContext } from "./FlagsContext";
import { ldReactContext } from "./ldReactContext";
import { toLDContext } from "./ldContext";

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
 * Starts the LaunchDarkly client once the signed-in user is known.
 *
 * Starting it earlier would make the SDK evaluate an anonymous context first, and each
 * anonymous context counts as one more client-side monthly active user.
 *
 * Must be placed inside `AuthProvider` and around {@link LDIdentifier}, the only reader of
 * the client.
 */
export function LDUserProvider({ children }) {
  const { user } = useAuth();
  const context = useMemo(() => (user ? toLDContext(user) : undefined), [user]);

  return (
    <LDProvider
      clientSideID={import.meta.env.VITE_LAUNCHDARKLY_CLIENT_ID}
      context={context}
      deferInitialization
      reactOptions={{ reactContext: ldReactContext }}
    >
      {children}
    </LDProvider>
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
 * instance that {@link LDUserProvider} writes to, regardless of bundle chunk boundaries.
 */
export function LDIdentifier() {
  const ldClient = useLDClient(ldReactContext);
  const { user } = useAuth();
  const { setFlags, setReady } = useContext(FlagsContext);

  useEffect(() => {
    if (!ldClient || !user) return;

    ldClient
      .identify(toLDContext(user))
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
