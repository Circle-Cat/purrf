import { createContext, useContext } from "react";

/**
 * What's new state for the account menu. Outside a WhatsNewProvider, or while
 * the feature is off, `enabled` is false and the actions do nothing.
 *
 * @type {React.Context<{
 *   enabled: boolean,
 *   unreadCount: number,
 *   showIntro: boolean,
 *   openPanel: () => void,
 *   acknowledgeIntro: () => void,
 *   hideIntro: () => void,
 * }>}
 */
export const WhatsNewContext = createContext({
  enabled: false,
  unreadCount: 0,
  showIntro: false,
  openPanel: () => {},
  acknowledgeIntro: () => {},
  hideIntro: () => {},
});

/**
 * Access the What's new state shared by the header and the panel.
 *
 * @returns {{
 *   enabled: boolean,
 *   unreadCount: number,
 *   showIntro: boolean,
 *   openPanel: () => void,
 *   acknowledgeIntro: () => void,
 *   hideIntro: () => void,
 * }} `unreadCount` counts visible entries the viewer has never seen in the
 *   panel; `showIntro` is true while the one-time pointer should show;
 *   `acknowledgeIntro` records that pointer as done; `hideIntro` hides it for
 *   this page load only.
 */
export const useWhatsNew = () => useContext(WhatsNewContext);
