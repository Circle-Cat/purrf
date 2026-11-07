import { createContext, useContext } from "react";

/**
 * Onboarding guide context. Outside a GuideProvider (or while it is inactive)
 * `active` is false and `start` does nothing.
 *
 * @type {React.Context<{active: boolean, start: (key: string) => void}>}
 */
export const GuideContext = createContext({
  active: false,
  start: () => {},
});

/**
 * Access the onboarding guide engine.
 *
 * @returns {{active: boolean, start: (key: string) => void}} `active` is true
 *   when a guide can run here (signed in, verified, no auth error); `start`
 *   replays a guide on demand.
 */
export const useGuides = () => useContext(GuideContext);
