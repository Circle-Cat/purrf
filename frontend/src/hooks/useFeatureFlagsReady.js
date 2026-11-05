import { useContext } from "react";
import { FlagsContext } from "@/context/flags";

/**
 * Whether LaunchDarkly has answered for the current user, successfully or not.
 *
 * Until then every flag reads as off, so anything that acts on a flag being off
 * -- a redirect, an "unavailable" message -- should wait for this first.
 *
 * @returns {boolean} True once flag values are settled.
 */
export function useFeatureFlagsReady() {
  const { ready } = useContext(FlagsContext);
  return ready;
}
