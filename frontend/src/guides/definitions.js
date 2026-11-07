/**
 * Every onboarding guide the app knows about.
 *
 * A step's `anchor` names the element it highlights: the element carries
 * `data-tour="<anchor>"`. `before` names a layout action the GuideProvider
 * runs before showing that step (see its `actions` prop). A step with
 * `navGroup` has no fixed body: it lists what the viewer can see in that
 * sidebar group (see `resolveSteps`). `audience` receives
 * `{ permissions, flags }` and decides whether the guide applies to the viewer.
 *
 * @type {Array<{
 *   key: string,
 *   type: "tour",
 *   priority: number,
 *   audience: (ctx: {permissions: string[], flags: Record<string, any>}) => boolean,
 *   trigger: {kind: "first-visit"},
 *   steps: Array<{
 *     anchor: string,
 *     title: string,
 *     body?: string,
 *     navGroup?: string,
 *     before?: string,
 *   }>,
 * }>}
 */
export const GUIDES = [
  {
    key: "welcome",
    type: "tour",
    priority: 100,
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
        title: "Your dashboard",
        body: "Personal Dashboard gathers what is yours: your applications, and your mentorship and time off if they apply to you.",
        before: "expand-sidebar",
      },
      {
        anchor: "nav-group-apply",
        title: "Open Positions",
        body: "Every Circle Cat activity and job opening is listed here. Open one to read the details and apply.",
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
      {
        anchor: "avatar-menu",
        title: "That's it for now",
        body: "Each page explains itself the first time you open it. You can take this tour again from the avatar menu.",
      },
    ],
  },
];
