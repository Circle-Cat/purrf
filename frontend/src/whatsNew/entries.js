import { ROUTE_PATHS } from "@/constants/RoutePaths";

/**
 * What's new entries: undated ones (not yet in production) first, then dated
 * ones newest first. The panel opened from the account menu
 * lists every entry whose `audience` accepts the viewer.
 *
 * To announce a feature, add an object to the top of this array in the same
 * PR that ships it:
 *
 * - `id`: a stable slug of lowercase letters, digits and hyphens, at most 50
 *   characters, and not `intro`. It keys the viewer's read state on the
 *   server, so never rename or reuse it: a new id reads as unread for
 *   everyone.
 * - `date` (filled in at release): `YYYY-MM-DD`, the day the feature
 *   reached production, i.e. the date of the `release/<date>` tag that ships
 *   it. Leave it out in the feature PR; whoever cuts that release adds it.
 *   An entry without a date is still listed, just without one, above the
 *   dated entries.
 * - `title`: at most 40 characters.
 * - `body`: one or two plain English sentences saying what the user can now
 *   do and how to get there. Only claim what the code supports. Wrap words
 *   in `**` to show them in bold, e.g. a menu item's name.
 * - `showMe.route`: the page the "Show me" link opens, from ROUTE_PATHS.
 * - `showMe.anchor`: put `data-whats-new="<anchor>"` on the element to point
 *   at in that page's component. It is scrolled into view and outlined; if it
 *   never renders, the user is simply left on the page.
 * - `flag` (required when the feature is behind a LaunchDarkly flag): the
 *   flag's key from FEATURE_FLAGS. The entry is shown only where that flag is
 *   on, so it never announces something the viewer cannot use yet.
 * - `audience(viewer)` (optional): returns true for viewers who should see
 *   the entry. `viewer` is `{ permissions, flags }`: the caller's permission
 *   strings and the LaunchDarkly flag values. Leave it out for everyone.
 *
 * Every entry counts as unread for every viewer until they open the panel,
 * including people who sign up after the entry was added.
 *
 * @type {ReadonlyArray<{
 *   id: string,
 *   date?: string,
 *   title: string,
 *   body: string,
 *   showMe: { route: string, anchor: string },
 *   flag?: string,
 *   audience?: (viewer: { permissions: string[], flags: Record<string, any> }) => boolean,
 * }>}
 */
export const WHATS_NEW_ENTRIES = Object.freeze([
  {
    id: "sign-in-with-any-email",
    date: "2026-11-05",
    title: "Sign in with any email address",
    body: "Click your avatar in the top right and select **Emails & sign-in**. Add a new email address, enter the verification code to confirm it, and you\u2019re all set\u2014you can now use it to sign in to the same Purrf account.",
    showMe: { route: ROUTE_PATHS.SIGN_IN_SECURITY, anchor: "add-email" },
  },
]);
