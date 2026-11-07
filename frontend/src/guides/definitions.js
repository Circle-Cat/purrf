/**
 * Every onboarding guide the app knows about.
 *
 * A step's `anchor` names the element it highlights: the element carries
 * `data-tour="<anchor>"`. A step whose anchor is not on the page is skipped,
 * so a step list can hold variants of one step for different page states;
 * variants share an `alternative` name, and the component renders exactly one
 * of their anchors. `before` names a layout action the GuideProvider runs
 * before showing that step (see its `actions` prop). A step with `navGroup`
 * has no fixed body: it lists what the viewer can see in that sidebar group
 * (see `resolveSteps`). A step with `when` shows only when it returns true.
 *
 * `audience` and `when` receive `{ permissions, flags, mentorshipRoles }`.
 *
 * A guide of type "tour" runs on one page. With trigger "first-visit" it
 * starts on its own once (until completed or dismissed), unless
 * `trigger.skipIf(location)` says not here, its `route` (if any) does not
 * match, or its `requires.seen` guide is not yet completed or dismissed. An
 * auto-started tour needs two visible steps unless its `kind` is
 * "new-feature". `basics: true` marks the basics tour: completing it leads
 * into the tasks, and replaying it from the avatar menu resets page intros.
 *
 * A guide of type "task" (key `task-<name>`) walks several pages in
 * `segments`. Each segment names its `route` (a React Router pattern; the
 * engine navigates there itself) and, when that pattern has params,
 * `params(viewer)` to fill them, which may read the page the previous
 * segment showed; a segment whose route cannot be resolved, or whose anchors
 * do not render in time, is skipped. A task runs only when the viewer picks
 * it from the chooser offered after the basics tour (or once they newly
 * qualify for it), but each of its segments doubles as the intro of its
 * page: opened by
 * the viewer, the page shows that segment alone, stored under
 * `page-<segment key>`, until the viewer has seen it or completed the task.
 *
 * @typedef {{
 *   anchor: string,
 *   title: string,
 *   body?: string,
 *   navGroup?: string,
 *   before?: string,
 *   alternative?: string,
 *   when?: (viewer: Object) => boolean,
 * }} GuideStep
 *
 * @type {Array<{
 *   key: string,
 *   type: "tour" | "task",
 *   title?: string,
 *   priority: number,
 *   kind?: "new-feature",
 *   basics?: boolean,
 *   route?: string,
 *   requires?: {seen: string},
 *   audience: (viewer: {permissions: string[], flags: Record<string, any>, mentorshipRoles: string[]}) => boolean,
 *   trigger?: {kind: "first-visit", skipIf?: (location: Object) => boolean},
 *   steps?: GuideStep[],
 *   segments?: Array<{
 *     key: string,
 *     route: string,
 *     params?: (viewer: Object) => Record<string, string> | null,
 *     steps: GuideStep[],
 *   }>,
 * }>}
 */
export const GUIDES = [
  {
    key: "welcome",
    type: "tour",
    priority: 100,
    basics: true,
    audience: () => true,
    trigger: { kind: "first-visit" },
    steps: [
      {
        anchor: "avatar-menu",
        title: "Your account menu",
        body: "Click your avatar to view your profile, manage your emails and sign-in methods, contact the admins, take this tour again, or log out.",
      },
      {
        anchor: "nav-group-me",
        title: "Your home page",
        navGroup: "me",
        before: "expand-sidebar",
      },
      {
        anchor: "nav-group-apply",
        title: "Open Positions",
        navGroup: "apply",
        before: "expand-sidebar",
      },
      {
        anchor: "nav-group-recruiting",
        title: "Recruiting",
        navGroup: "recruiting",
        before: "expand-sidebar",
      },
      {
        anchor: "nav-group-mentorship",
        title: "Mentorship",
        navGroup: "mentorship",
        before: "expand-sidebar",
      },
      {
        anchor: "nav-group-activity",
        title: "Activity data",
        navGroup: "activity",
        before: "expand-sidebar",
      },
      {
        anchor: "nav-group-admin",
        title: "Administration",
        navGroup: "admin",
        before: "expand-sidebar",
      },
    ],
  },
];
