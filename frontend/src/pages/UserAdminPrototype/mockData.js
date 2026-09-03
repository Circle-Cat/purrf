/**
 * Placeholder people and state for the user-admin prototype.
 *
 * This bundle is published to a public URL, so every name, address and reason
 * here is invented. The set is chosen to cover each combination the console
 * has to render rather than to look like a realistic roster: active, blocked,
 * deactivated, both at once, super admin, internal, external, and one account
 * whose only sign-in history is passwordless (no identity rows at all).
 */

/** The operator the prototype signs you in as. Self-protection keys off this. */
export const CURRENT_USER_ID = 1042;

/** Rendered wherever an actor id has to become a name. */
export const ACTOR_NAMES = {
  1042: "Wang, Yanpei",
  1077: "Okonkwo, Ada",
  1090: "Silva, Marco",
};

const email = (local) => `${local}@example.com`;

export const INITIAL_USERS = [
  {
    userId: 1042,
    firstName: "Wang",
    lastName: "Yanpei",
    preferredName: "Yuji",
    contactEmail: "yuji@circlecat.org",
    userType: "internal",
    isSuperAdmin: true,
    createdOn: "2024-01-08",
    isActive: true,
    deactivatedAt: null,
    deactivatedBy: null,
    deactivatedReason: null,
    isBlocked: false,
    blockedAt: null,
    blockedBy: null,
    blockedReason: null,
    emails: [
      { address: "yuji@circlecat.org", confirmed: true, primary: true },
      { address: email("y.wang"), confirmed: true, primary: false },
    ],
    identities: [{ provider: "Google", claim: "yuji@circlecat.org" }],
  },
  {
    userId: 1077,
    firstName: "Okonkwo",
    lastName: "Ada",
    preferredName: null,
    contactEmail: "ada@circlecat.org",
    userType: "internal",
    isSuperAdmin: false,
    createdOn: "2024-06-02",
    isActive: true,
    deactivatedAt: null,
    deactivatedBy: null,
    deactivatedReason: null,
    isBlocked: false,
    blockedAt: null,
    blockedBy: null,
    blockedReason: null,
    emails: [{ address: "ada@circlecat.org", confirmed: true, primary: true }],
    identities: [{ provider: "Google", claim: "ada@circlecat.org" }],
  },
  {
    userId: 1130,
    firstName: "Chen",
    lastName: "Lin",
    preferredName: "Lin",
    contactEmail: email("lin.chen"),
    userType: "external",
    isSuperAdmin: false,
    createdOn: "2025-11-19",
    isActive: true,
    deactivatedAt: null,
    deactivatedBy: null,
    deactivatedReason: null,
    isBlocked: true,
    blockedAt: "2026-07-14",
    blockedBy: 1042,
    blockedReason: "Repeated no-shows after three rescheduled interviews.",
    emails: [{ address: email("lin.chen"), confirmed: true, primary: true }],
    identities: [{ provider: "Google", claim: email("lin.chen") }],
  },
  {
    userId: 1203,
    firstName: "Zhao",
    lastName: "Min",
    preferredName: "Min",
    contactEmail: email("min.zhao"),
    userType: "external",
    isSuperAdmin: false,
    createdOn: "2026-03-11",
    isActive: false,
    deactivatedAt: "2026-08-20",
    deactivatedBy: 1042,
    deactivatedReason: "Asked by email to close the account.",
    isBlocked: false,
    blockedAt: null,
    blockedBy: null,
    blockedReason: null,
    emails: [
      { address: email("min.zhao"), confirmed: true, primary: true },
      { address: email("minzhao.personal"), confirmed: false, primary: false },
    ],
    identities: [{ provider: "Google", claim: email("min.zhao") }],
  },
  {
    userId: 1250,
    firstName: "Liu",
    lastName: "Kai",
    preferredName: null,
    contactEmail: email("kai.liu"),
    userType: "external",
    isSuperAdmin: false,
    createdOn: "2025-02-27",
    isActive: false,
    deactivatedAt: "2026-05-02",
    deactivatedBy: 1090,
    deactivatedReason: "Left the programme and asked to be removed.",
    isBlocked: true,
    blockedAt: "2026-04-28",
    blockedBy: 1090,
    blockedReason: "Abusive language toward a mentor in written feedback.",
    emails: [{ address: email("kai.liu"), confirmed: true, primary: true }],
    identities: [],
  },
  {
    userId: 1311,
    firstName: "Nakamura",
    lastName: "Rei",
    preferredName: "Rei",
    contactEmail: email("rei.nakamura"),
    userType: "external",
    isSuperAdmin: false,
    createdOn: "2026-01-30",
    isActive: true,
    deactivatedAt: null,
    deactivatedBy: null,
    deactivatedReason: null,
    isBlocked: false,
    blockedAt: null,
    blockedBy: null,
    blockedReason: null,
    emails: [
      { address: email("rei.nakamura"), confirmed: true, primary: true },
    ],
    identities: [],
  },
  {
    userId: 1364,
    firstName: "Silva",
    lastName: "Marco",
    preferredName: null,
    contactEmail: "marco@circlecat.org",
    userType: "internal",
    isSuperAdmin: false,
    createdOn: "2023-09-15",
    isActive: true,
    deactivatedAt: null,
    deactivatedBy: null,
    deactivatedReason: null,
    isBlocked: false,
    blockedAt: null,
    blockedBy: null,
    blockedReason: null,
    emails: [
      { address: "marco@circlecat.org", confirmed: true, primary: true },
    ],
    identities: [{ provider: "Google", claim: "marco@circlecat.org" }],
  },
  {
    userId: 1402,
    firstName: "Osei",
    lastName: "Kwame",
    preferredName: "Kwame",
    contactEmail: email("kwame.osei"),
    userType: "external",
    isSuperAdmin: false,
    createdOn: "2026-02-14",
    isActive: true,
    deactivatedAt: null,
    deactivatedBy: null,
    deactivatedReason: null,
    isBlocked: false,
    blockedAt: null,
    blockedBy: null,
    blockedReason: null,
    emails: [{ address: email("kwame.osei"), confirmed: true, primary: true }],
    identities: [{ provider: "Google", claim: email("kwame.osei") }],
  },
  {
    userId: 1455,
    firstName: "Ivanova",
    lastName: "Dasha",
    preferredName: null,
    contactEmail: email("dasha.ivanova"),
    userType: "external",
    isSuperAdmin: false,
    createdOn: "2025-08-08",
    isActive: true,
    deactivatedAt: null,
    deactivatedBy: null,
    deactivatedReason: null,
    isBlocked: false,
    blockedAt: null,
    blockedBy: null,
    blockedReason: null,
    emails: [
      { address: email("dasha.ivanova"), confirmed: true, primary: true },
      { address: email("d.ivanova.alt"), confirmed: true, primary: false },
    ],
    identities: [{ provider: "Google", claim: email("dasha.ivanova") }],
  },
  {
    userId: 1508,
    firstName: "Park",
    lastName: "Jisoo",
    preferredName: "Jisoo",
    contactEmail: email("jisoo.park"),
    userType: "external",
    isSuperAdmin: false,
    createdOn: "2026-04-22",
    isActive: true,
    deactivatedAt: null,
    deactivatedBy: null,
    deactivatedReason: null,
    isBlocked: false,
    blockedAt: null,
    blockedBy: null,
    blockedReason: null,
    emails: [{ address: email("jisoo.park"), confirmed: true, primary: true }],
    identities: [{ provider: "Google", claim: email("jisoo.park") }],
  },
  {
    userId: 1560,
    firstName: "Haddad",
    lastName: "Nour",
    preferredName: null,
    contactEmail: email("nour.haddad"),
    userType: "external",
    isSuperAdmin: false,
    createdOn: "2025-12-03",
    isActive: true,
    deactivatedAt: null,
    deactivatedBy: null,
    deactivatedReason: null,
    isBlocked: false,
    blockedAt: null,
    blockedBy: null,
    blockedReason: null,
    emails: [
      { address: email("nour.haddad"), confirmed: false, primary: true },
    ],
    identities: [],
  },
  {
    userId: 1614,
    firstName: "Andersen",
    lastName: "Freja",
    preferredName: "Freja",
    contactEmail: email("freja.andersen"),
    userType: "external",
    isSuperAdmin: false,
    createdOn: "2026-06-17",
    isActive: true,
    deactivatedAt: null,
    deactivatedBy: null,
    deactivatedReason: null,
    isBlocked: false,
    blockedAt: null,
    blockedBy: null,
    blockedReason: null,
    emails: [
      { address: email("freja.andersen"), confirmed: true, primary: true },
    ],
    identities: [{ provider: "Google", claim: email("freja.andersen") }],
  },
];

/**
 * What a block would sweep, keyed by user. The console reads this to build the
 * pre-flight so an approver can see the consequences before deciding.
 *
 * Interviews and meetings are dates without titles: how large the consequence
 * is and how soon it lands are the operator's business, which posting someone
 * applied to is not. Pairs carry the partner's name because ending the pair
 * costs that person a partner mid-round.
 */
export const BLOCK_IMPACT = {
  1130: {
    applications: 3,
    interviews: ["2026-09-08 14:00", "2026-09-11 10:00"],
    pairs: [],
    mentorshipMeetings: [],
  },
  1311: {
    applications: 2,
    interviews: ["2026-09-05 09:30"],
    pairs: ["Silva, Marco"],
    mentorshipMeetings: ["2026-09-04 16:00", "2026-09-11 16:00"],
  },
  1402: {
    applications: 1,
    interviews: [],
    pairs: ["Okonkwo, Ada"],
    mentorshipMeetings: ["2026-09-06 11:00"],
  },
  1508: {
    applications: 1,
    interviews: ["2026-09-09 13:00"],
    pairs: [],
    mentorshipMeetings: [],
  },
};

/** Zero impact is the common case; the console still shows it explicitly. */
export const EMPTY_IMPACT = {
  applications: 0,
  interviews: [],
  pairs: [],
  mentorshipMeetings: [],
};

/** One request already waiting, so the console does not open empty. */
export const INITIAL_REQUESTS = [
  {
    id: 9001,
    targetUserId: 1311,
    raisedBy: "Okonkwo, Ada",
    raisedFrom: "Mentorship management",
    raisedOn: "2026-09-01",
    reason:
      "Second no-show in the same round; mentor filed a red flag after the missed session on 2026-08-27.",
    status: "pending",
    decidedBy: null,
    decidedOn: null,
    decisionNote: null,
  },
];

/** The candidates a recruiter can act on, for the request-raising view. */
export const RECRUITING_ROWS = [
  { userId: 1508, posting: "Data Analyst", stage: "Screening" },
  { userId: 1455, posting: "Backend Engineer", stage: "Interview" },
  { userId: 1614, posting: "Backend Engineer", stage: "Applied" },
];

/** The pairs a mentorship admin can act on, for the request-raising view. */
export const MENTORSHIP_ROWS = [
  { userId: 1311, role: "Mentee", partner: "Silva, Marco", noShows: 2 },
  { userId: 1402, role: "Mentee", partner: "Okonkwo, Ada", noShows: 0 },
  { userId: 1364, role: "Mentor", partner: "Osei, Kwame", noShows: 0 },
];
