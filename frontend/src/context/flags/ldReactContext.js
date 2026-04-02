import { createContext } from "react";

/**
 * Shared React context for the LaunchDarkly React SDK.
 *
 * Passed explicitly to `withLDProvider` (via `reactOptions.reactContext`) and to
 * `useLDClient(ldReactContext)` so that both sides reference the same context instance.
 *
 * Without this, the Bazel/esbuild production build can place `withLDProvider` and
 * `useLDClient` in separate bundle chunks, each with their own copy of the SDK's
 * internal default context, causing `useLDClient()` to always return `undefined`.
 *
 * Shape matches `ReactSdkContext` from `launchdarkly-react-client-sdk`.
 */
export const ldReactContext = createContext({
  flags: {},
  flagKeyMap: {},
  ldClient: undefined,
});
