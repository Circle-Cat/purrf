/**
 * Placeholder rounds, people, pairs and notes for the mentorship admin prototype.
 *
 * This bundle is published to a public URL, so every name, address, reason and
 * feedback quote here is invented. The set is chosen to cover each combination
 * the console has to render rather than to look like a realistic roster:
 *
 *   - a mentor carrying two mentees (one row, two lines in its Pair column)
 *   - all four states of "meetings last round": first time, unmatched, 0, n/m
 *   - a pair that has made first contact and one that has not
 *   - an ended pair, so `inactive` renders somewhere
 *   - someone admitted but not yet registered, so the Not registered filter
 *     has a row
 *   - notes of all three kinds: written, decided-by-approval, system
 */

/** The admin the prototype signs you in as. */
export const CURRENT_USER = { userId: 2001, name: "Jiang, Goose" };

/**
 * Everyone holding `mentorship.approve`. A request names one of them so it is
 * addressed to a person, but any of them may decide it — except whoever
 * raised it.
 */
export const APPROVE_HOLDERS = [
  { userId: 2001, name: "Jiang, Goose", email: "goose@circlecat.org" },
  { userId: 2002, name: "Wang, Jasmine", email: "jasmine@circlecat.org" },
  { userId: 2003, name: "Wang, Yanpei", email: "yanpei@circlecat.org" },
];

/** Rendered wherever an actor id has to become a name. */
export const ACTOR_NAMES = {
  2001: "Jiang, Goose",
  2002: "Wang, Jasmine",
  2003: "Wang, Yanpei",
};

/**
 * Which permissions the viewer holds.
 *
 * The prototype lets you toggle these, because the single hardest thing to
 * convey in writing is that three different people see three different pages:
 * the approver sees a card the admin does not, and feedback is a separate
 * grant from the rest of the console.
 */
export const ALL_PERMISSIONS = [
  { key: "mentorship.admin.read", label: "Read" },
  { key: "mentorship.admin.write", label: "Write" },
  { key: "mentorship.approve", label: "Approve" },
  { key: "mentorship.feedback.read", label: "Feedback" },
];

export const DEFAULT_PERMISSIONS = [
  "mentorship.admin.read",
  "mentorship.admin.write",
  "mentorship.approve",
  "mentorship.feedback.read",
];

/**
 * Rounds carry the timeline field set as redesigned, not as shipped:
 *
 *   - `onboardingDeadlineAt` (renamed from trainingDeadlineAt) is the gate —
 *     it is both the onboarding deadline and the round registration deadline
 *   - `*ApplicationDeadlineAt` is the *job* application deadline, which lives
 *     on the recruiting side and is shown here for reference only
 *   - `firstMeetingDeadlineAt` is restored; it is the date a mentee must have
 *     emailed their mentor by
 *   - `matchingCompletedAt` is stamped by the system when a matching run is
 *     published, so it is not on the form at all
 */
export const INITIAL_ROUNDS = [
  {
    id: 7,
    name: "Mentorship 2026 Fall",
    version: "v2",
    requiredMeetings: 5,
    status: "active",
    timeline: {
      promotionStartAt: "2026-08-18",
      mentorApplicationDeadlineAt: "2026-08-25",
      menteeApplicationDeadlineAt: "2026-08-25",
      onboardingNotificationAt: "2026-09-02",
      onboardingDeadlineAt: "2026-09-09",
      matchNotificationAt: "2026-09-30",
      firstMeetingDeadlineAt: "2026-09-19",
      meetingLogReminderAt: "2026-11-02",
      meetingsCompletionDeadlineAt: "2026-11-30",
      feedbackStartAt: "2026-12-02",
      feedbackDeadlineAt: "2026-12-09",
    },
    matchingCompletedAt: "2026-09-11",
  },
  {
    id: 6,
    name: "Mentorship 2025 Summer",
    version: "v1",
    requiredMeetings: 7,
    status: "closed",
    timeline: {
      promotionStartAt: "2025-04-18",
      mentorApplicationDeadlineAt: "2025-04-25",
      menteeApplicationDeadlineAt: "2025-04-25",
      onboardingNotificationAt: "2025-05-02",
      onboardingDeadlineAt: "2025-05-09",
      matchNotificationAt: "2025-05-12",
      firstMeetingDeadlineAt: "2025-05-19",
      meetingLogReminderAt: "2025-07-02",
      meetingsCompletionDeadlineAt: "2025-08-31",
      feedbackStartAt: "2025-09-02",
      feedbackDeadlineAt: "2025-09-09",
    },
    matchingCompletedAt: "2025-05-11",
  },
];

/**
 * One row per person per round.
 *
 * "Meetings last round" is not stored on these rows: it is read from the
 * person's latest earlier registration and that round's pairs.
 */
export const INITIAL_PARTICIPANTS = [
  {
    participantId: "p-alice-7",
    userId: 3101,
    roundId: 7,
    name: "Chen, Alice",
    email: "alice@example.com",
    role: "mentee",
    identity: "external",
    approvalStatus: "signed_up",
    onboardingDone: true,
  },
  {
    participantId: "p-bob-7",
    userId: 3102,
    roundId: 7,
    name: "Liu, Bob",
    email: "bob@circlecat.org",
    role: "mentor",
    identity: "internal",
    approvalStatus: "matched",
    maxPartners: 3,
    onboardingDone: true,
  },
  {
    participantId: "p-cara-7",
    userId: 3103,
    roundId: 7,
    name: "Wang, Cara",
    email: "cara@example.com",
    role: "mentee",
    identity: "external",
    approvalStatus: "matched",
    onboardingDone: true,
  },
  {
    participantId: "p-dana-7",
    userId: 3104,
    roundId: 7,
    name: "Wu, Dana",
    email: "dana@circlecat.org",
    role: "mentee",
    identity: "internal",
    approvalStatus: "signed_up",
    onboardingDone: true,
  },
  {
    participantId: "p-ivy-7",
    userId: 3110,
    roundId: 7,
    name: "Hu, Ivy",
    email: "ivy@example.com",
    role: "mentee",
    identity: "external",
    approvalStatus: "signed_up",
    onboardingDone: false,
  },
  {
    participantId: "p-erin-7",
    userId: 3105,
    roundId: 7,
    name: "Ma, Erin",
    email: "erin@example.com",
    role: "mentee",
    identity: "external",
    approvalStatus: "matched",
    onboardingDone: true,
  },
  {
    participantId: "p-fay-7",
    userId: 3106,
    roundId: 7,
    name: "Guo, Fay",
    email: "fay@circlecat.org",
    role: "mentor",
    identity: "internal",
    approvalStatus: "matched",
    maxPartners: 2,
    onboardingDone: true,
  },
  {
    participantId: "p-gina-7",
    userId: 3107,
    roundId: 7,
    name: "Shen, Gina",
    email: "gina@example.com",
    role: "mentee",
    identity: "external",
    approvalStatus: "withdrawn",
    onboardingDone: true,
  },
  // Signed up and onboarded, but their past needs an exemption first: Sora
  // met 3 of 7 last time, Wei has a red flag from last summer.
  {
    participantId: "p-sora-7",
    userId: 3114,
    roundId: 7,
    name: "Kim, Sora",
    email: "sora@example.com",
    role: "mentee",
    identity: "external",
    approvalStatus: "signed_up",
    onboardingDone: true,
  },
  {
    participantId: "p-wei-7",
    userId: 3115,
    roundId: 7,
    name: "Tan, Wei",
    email: "wei@circlecat.org",
    role: "mentee",
    identity: "internal",
    approvalStatus: "signed_up",
    onboardingDone: true,
  },
  // Registered and onboarded, but blocked: never offered to matching.
  {
    participantId: "p-oscar-7",
    userId: 3113,
    roundId: 7,
    name: "Lin, Oscar",
    email: "oscar@example.com",
    role: "mentee",
    identity: "external",
    approvalStatus: "signed_up",
    onboardingDone: true,
  },
  // Cara's history row, so the participant detail page has more than one round.
  {
    participantId: "p-cara-6",
    userId: 3103,
    roundId: 6,
    name: "Wang, Cara",
    email: "cara@example.com",
    role: "mentee",
    identity: "external",
    approvalStatus: "matched",
    onboardingDone: true,
  },
  {
    participantId: "p-sora-6",
    userId: 3114,
    roundId: 6,
    name: "Kim, Sora",
    email: "sora@example.com",
    role: "mentee",
    identity: "external",
    approvalStatus: "matched",
    onboardingDone: true,
  },
  {
    participantId: "p-wei-6",
    userId: 3115,
    roundId: 6,
    name: "Tan, Wei",
    email: "wei@circlecat.org",
    role: "mentee",
    identity: "internal",
    approvalStatus: "un_matched",
    onboardingDone: true,
  },
  // Last summer, so this round's "Meetings last round" has something to read:
  // Dana mentored Cara to the end, Bob was not matched, Fay withdrew part
  // way, and Gina's pair ended with her.
  {
    participantId: "p-dana-6",
    userId: 3104,
    roundId: 6,
    name: "Wu, Dana",
    email: "dana@circlecat.org",
    role: "mentor",
    identity: "internal",
    approvalStatus: "matched",
    maxPartners: 1,
    onboardingDone: true,
  },
  {
    participantId: "p-bob-6",
    userId: 3102,
    roundId: 6,
    name: "Liu, Bob",
    email: "bob@circlecat.org",
    role: "mentor",
    identity: "internal",
    approvalStatus: "un_matched",
    maxPartners: 2,
    onboardingDone: true,
  },
  {
    participantId: "p-fay-6",
    userId: 3106,
    roundId: 6,
    name: "Guo, Fay",
    email: "fay@circlecat.org",
    role: "mentor",
    identity: "internal",
    approvalStatus: "withdrawn",
    maxPartners: 1,
    onboardingDone: true,
  },
  {
    participantId: "p-gina-6",
    userId: 3107,
    roundId: 6,
    name: "Shen, Gina",
    email: "gina@example.com",
    role: "mentee",
    identity: "external",
    approvalStatus: "matched",
    onboardingDone: true,
  },
  // Took part last summer and has not signed up for this round.
  {
    participantId: "p-min-6",
    userId: 3111,
    roundId: 6,
    name: "Park, Min",
    email: "min@circlecat.org",
    role: "mentor",
    identity: "internal",
    approvalStatus: "matched",
    maxPartners: 1,
    onboardingDone: true,
  },
];

/**
 * Admissions: a hired application to a mentor or mentee posting.
 *
 * This, together with having registered for some round (which covers the
 * historical backfill), is what "in the programme" means. A job is not tied
 * to a round, so an admission counts for every round after it.
 */
export const HIRED_APPLICATIONS = [
  { userId: 3101, role: "mentee" },
  { userId: 3105, role: "mentee" },
  { userId: 3108, role: "mentee" },
  { userId: 3109, role: "mentor" },
  { userId: 3110, role: "mentee" },
  { userId: 3113, role: "mentee" },
];

/**
 * Mentorship onboarding courses, one row per person per role.
 *
 * Not a way into the programme — a course can be handed out on its own, as
 * Zhou, Tao's was. It is what a registered person must have finished for
 * their role, and what an onboarding reminder chases.
 */
export const ONBOARDING_TRAININGS = [
  { userId: 3101, role: "mentee", status: "done" },
  { userId: 3102, role: "mentor", status: "done" },
  { userId: 3103, role: "mentee", status: "done" },
  { userId: 3104, role: "mentor", status: "done" },
  { userId: 3104, role: "mentee", status: "done" },
  { userId: 3105, role: "mentee", status: "done" },
  { userId: 3106, role: "mentor", status: "done" },
  { userId: 3107, role: "mentee", status: "done" },
  { userId: 3108, role: "mentee", status: "in_progress" },
  { userId: 3109, role: "mentor", status: "done" },
  { userId: 3110, role: "mentee", status: "in_progress" },
  { userId: 3111, role: "mentor", status: "done" },
  { userId: 3112, role: "mentor", status: "in_progress" },
  { userId: 3113, role: "mentee", status: "done" },
  { userId: 3114, role: "mentee", status: "done" },
  { userId: 3115, role: "mentee", status: "done" },
];

/** Who the people with no registration anywhere are. */
export const NEVER_REGISTERED = [
  {
    userId: 3108,
    name: "Osei, Kwame",
    email: "kwame@example.com",
    identity: "external",
  },
  {
    userId: 3109,
    name: "Rossi, Lia",
    email: "lia@circlecat.org",
    identity: "internal",
  },
  {
    userId: 3112,
    name: "Zhou, Tao",
    email: "tao@circlecat.org",
    identity: "internal",
  },
];

/**
 * Account state, per person rather than per round — the same two flags the
 * accounts console shows. They are independent: an account can be blocked and
 * deactivated at once. Anyone missing here is active and not blocked.
 */
export const ACCOUNT_STATES = {
  3107: { isActive: true, isBlocked: true },
  3109: { isActive: false, isBlocked: true },
  3110: { isActive: false, isBlocked: false },
  3113: { isActive: true, isBlocked: true },
};

export const accountStateOf = (userId) =>
  ACCOUNT_STATES[userId] ?? { isActive: true, isBlocked: false };

/**
 * What the review screen shows for each side of a proposed pair: their
 * résumé as held on their profile, and their answers to the mentorship
 * application. The real page reuses the profile's experience view and the
 * recruiting console's answers section rather than drawing new ones.
 */
export const PROFILES = {
  3101: {
    headline: "Data analyst moving into ML engineering",
    workHistory: [
      {
        title: "Data Analyst",
        company: "Northwind Health",
        years: "2023 – now",
      },
      { title: "BI Intern", company: "Contoso", years: "2022" },
    ],
    education: [{ degree: "BSc Statistics", school: "UC Davis" }],
    answers: [
      {
        q: "What do you want to get out of this round?",
        a: "A plan for moving from analytics into an ML engineering role within a year.",
      },
      {
        q: "Which skills do you most want to build?",
        a: "Production ML, system design, interviewing.",
      },
    ],
  },
  3104: {
    headline: "Backend engineer, three years in, wants to lead",
    workHistory: [
      {
        title: "Software Engineer",
        company: "Circle Cat",
        years: "2023 – now",
      },
    ],
    education: [
      { degree: "BEng Computer Science", school: "Zhejiang University" },
    ],
    answers: [
      {
        q: "What do you want to get out of this round?",
        a: "How to take on tech-lead responsibilities without dropping delivery.",
      },
      {
        q: "Which skills do you most want to build?",
        a: "Technical leadership, stakeholder management.",
      },
    ],
  },
  3110: {
    headline: "New grad, frontend",
    workHistory: [
      { title: "Frontend Intern", company: "Fabrikam", years: "2025" },
    ],
    education: [
      { degree: "BSc Computer Science", school: "University of Toronto" },
    ],
    answers: [
      {
        q: "What do you want to get out of this round?",
        a: "Landing a first full-time role.",
      },
      {
        q: "Which skills do you most want to build?",
        a: "Interviewing, portfolio, React performance.",
      },
    ],
  },
  3102: {
    headline: "Staff engineer, ML platform",
    workHistory: [
      {
        title: "Staff Software Engineer",
        company: "Circle Cat",
        years: "2019 – now",
      },
      { title: "ML Engineer", company: "Litware", years: "2015 – 2019" },
    ],
    education: [{ degree: "MS Computer Science", school: "Georgia Tech" }],
    answers: [
      {
        q: "Who would you most like to mentor?",
        a: "People moving into ML from analytics or research.",
      },
      {
        q: "How much time can you give each month?",
        a: "Two hours per mentee.",
      },
    ],
  },
  3106: {
    headline: "Engineering manager, backend",
    workHistory: [
      {
        title: "Engineering Manager",
        company: "Circle Cat",
        years: "2020 – now",
      },
      { title: "Senior Engineer", company: "Adatum", years: "2016 – 2020" },
    ],
    education: [
      { degree: "BEng Software Engineering", school: "Tongji University" },
    ],
    answers: [
      {
        q: "Who would you most like to mentor?",
        a: "Engineers stepping into their first lead role.",
      },
      {
        q: "How much time can you give each month?",
        a: "One hour per mentee, flexible.",
      },
    ],
  },
};

/**
 * What the matcher would say for a pairing, in the prototype. The real
 * reasons come from the matcher and are capped at 300 characters on write.
 */
export const MATCH_REASONS = {
  "3101-3102":
    "Alice wants to move from analytics into ML engineering, and Bob built an ML platform after starting in ML engineering himself. He asked for mentees coming from analytics.",
  "3104-3106":
    "Dana wants to grow into a tech lead, and Fay manages backend engineers and asked for people stepping into their first lead role.",
  "3110-3106":
    "Ivy is looking for a first full-time role; Fay hires engineers and can speak to what interviewers look for.",
};

/**
 * The admission emails Purrf sent by itself, as the notification pipeline
 * records them. One per admission, tagged with the round the person was
 * admitted towards; mentors and mentees alike, and each carries the
 * onboarding course and its deadline. `failed` is the pipeline's own status.
 */
export const ADMISSION_NOTIFICATIONS = [
  {
    userId: 3101,
    roundId: 7,
    event: "mentorship_admitted",
    status: "delivered",
    at: "2026-08-27",
  },
  {
    userId: 3105,
    roundId: 7,
    event: "mentorship_admitted",
    status: "delivered",
    at: "2026-08-27",
  },
  {
    userId: 3108,
    roundId: 7,
    event: "mentorship_admitted",
    status: "delivered",
    at: "2026-08-28",
  },
  {
    userId: 3109,
    roundId: 7,
    event: "mentorship_admitted",
    status: "delivered",
    at: "2026-08-28",
  },
  {
    userId: 3110,
    roundId: 7,
    event: "mentorship_admitted",
    status: "failed",
    at: "2026-08-29",
  },
];

export const INITIAL_PAIRS = [
  {
    pairId: 501,
    roundId: 7,
    mentorId: 3102,
    menteeId: 3103,
    mentorName: "Liu, Bob",
    menteeName: "Wang, Cara",
    status: "active",
    firstContactConfirmedAt: null,
    completed: 0,
    required: 5,
  },
  {
    pairId: 502,
    roundId: 7,
    mentorId: 3102,
    menteeId: 3105,
    mentorName: "Liu, Bob",
    menteeName: "Ma, Erin",
    status: "active",
    firstContactConfirmedAt: "2026-09-12",
    completed: 3,
    required: 5,
  },
  {
    pairId: 503,
    roundId: 7,
    mentorId: 3106,
    menteeId: 3107,
    mentorName: "Guo, Fay",
    menteeName: "Shen, Gina",
    status: "inactive",
    firstContactConfirmedAt: "2026-09-10",
    completed: 5,
    required: 5,
  },
  {
    pairId: 490,
    roundId: 6,
    mentorId: 3104,
    menteeId: 3103,
    mentorName: "Wu, Dana",
    menteeName: "Wang, Cara",
    status: "active",
    firstContactConfirmedAt: "2025-05-15",
    completed: 7,
    required: 7,
  },
  {
    pairId: 491,
    roundId: 6,
    mentorId: 3106,
    menteeId: 3107,
    mentorName: "Guo, Fay",
    menteeName: "Shen, Gina",
    status: "inactive",
    firstContactConfirmedAt: "2025-05-16",
    completed: 2,
    required: 7,
  },
  {
    pairId: 492,
    roundId: 6,
    mentorId: 3111,
    menteeId: 3114,
    mentorName: "Park, Min",
    menteeName: "Kim, Sora",
    status: "active",
    firstContactConfirmedAt: "2025-05-18",
    completed: 3,
    required: 7,
  },
];

/** A meeting a few days out, so the log always has one still to come. */
const upcoming = (() => {
  const start = new Date(Date.now() + 5 * 24 * 3600 * 1000);
  start.setUTCHours(17, 0, 0, 0);
  const end = new Date(start.getTime() + 3600 * 1000);
  return { startDatetime: start.toISOString(), endDatetime: end.toISOString() };
})();

/**
 * Meetings in the shape the console's meeting log already reads: UTC
 * datetimes (shown in Pacific time), a completion flag, and the attendance
 * tags in `note`.
 */
export const INITIAL_MEETINGS = [
  {
    meetingId: "m-1",
    pairId: 502,
    startDatetime: "2026-08-30T17:00:00Z",
    endDatetime: "2026-08-30T18:00:00Z",
    createDatetime: "2026-08-24T02:11:00Z",
    isCompleted: false,
    note: ["mentee_absent"],
  },
  {
    meetingId: "m-2",
    pairId: 502,
    startDatetime: "2026-09-07T17:00:00Z",
    endDatetime: "2026-09-07T17:20:00Z",
    createDatetime: "2026-09-01T16:40:00Z",
    isCompleted: true,
    note: ["insufficient_duration"],
  },
  {
    meetingId: "m-3",
    pairId: 502,
    startDatetime: "2026-09-14T17:00:00Z",
    endDatetime: "2026-09-14T18:00:00Z",
    createDatetime: "2026-09-08T19:05:00Z",
    isCompleted: true,
    note: [],
  },
  {
    meetingId: "m-4",
    pairId: 502,
    ...upcoming,
    createDatetime: "2026-09-15T20:30:00Z",
    isCompleted: false,
    note: [],
  },
  {
    meetingId: "m-5",
    pairId: 503,
    startDatetime: "2026-09-10T16:00:00Z",
    endDatetime: "2026-09-10T17:00:00Z",
    createDatetime: "2026-09-04T03:12:00Z",
    isCompleted: true,
    note: [],
  },
  {
    meetingId: "m-6",
    pairId: 490,
    startDatetime: "2025-06-02T17:00:00Z",
    endDatetime: "2025-06-02T18:00:00Z",
    createDatetime: "2025-05-28T01:00:00Z",
    isCompleted: true,
    note: [],
  },
];

/**
 * Notes carry a tag of three different kinds, and the kind decides the entry:
 *
 *   recorded  — something that happened; written straight from the console
 *   decided   — a judgement with consequences; only an approval can create it
 *   system    — written by the service itself, no human entry at all
 */
export const NOTE_KIND = {
  no_show: "decided",
  red_flag: "decided",
  partner_change_request: "decided",
  matching_exemption: "decided",
  status_change: "system",
  onboarding_reminder: "recorded",
  first_contact_reminder: "recorded",
  mentor_check_in: "recorded",
  midterm_reminder: "recorded",
  admission_notice: "recorded",
  match_result_notice: "recorded",
  feedback_invite: "recorded",
  round_invitation: "recorded",
  final_followup: "recorded",
  first_contact: "recorded",
};

export const NOTE_LABELS = {
  no_show: "No show",
  red_flag: "Red flag",
  partner_change_request: "Partner change request",
  matching_exemption: "Matching exemption",
  status_change: "Status change",
  onboarding_reminder: "Onboarding reminder",
  first_contact_reminder: "First contact reminder",
  mentor_check_in: "Mentor check-in",
  midterm_reminder: "Mid-term reminder",
  final_followup: "Final follow-up",
  round_invitation: "Round invitation",
  admission_notice: "Admission & onboarding",
  match_result_notice: "Match result",
  feedback_invite: "Feedback invitation",
  first_contact: "First contact confirmed",
};

/** Tags an admin may write directly. The rest go through an approval. */
export const RECORDED_TAGS = Object.keys(NOTE_KIND).filter(
  (tag) => NOTE_KIND[tag] === "recorded",
);

/**
 * Notes hang off a person and a round, not off a registration: someone who has
 * not signed up yet can still have "invited on Teams, 9/18" written about
 * them, and when they do register that note is already on their timeline.
 */
export const INITIAL_NOTES = [
  {
    noteId: "n-8",
    userId: 3115,
    roundId: 6,
    pairId: null,
    tag: "red_flag",
    body: "Missed two agreed calls without notice; mentor raised it with the programme.",
    authorId: 2002,
    createdAt: "2025-06-20",
  },
  {
    noteId: "n-6",
    userId: 3104,
    roundId: 7,
    pairId: null,
    tag: "onboarding_reminder",
    body: "Reminded on Teams.",
    authorId: 2001,
    createdAt: "2026-09-07",
  },
  {
    noteId: "n-7",
    userId: 3103,
    roundId: 6,
    pairId: null,
    tag: "midterm_reminder",
    body: "",
    authorId: 2002,
    createdAt: "2025-07-02",
  },
  {
    noteId: "n-1",
    userId: 3103,
    roundId: 7,
    pairId: 501,
    tag: "no_show",
    body: "No response after the first-contact deadline. Email and Teams both tried.",
    authorId: 2002,
    createdAt: "2026-09-20",
  },
  {
    noteId: "n-3",
    userId: 3103,
    roundId: 7,
    pairId: null,
    tag: "status_change",
    body: "signed_up → matched when the Fall matching run was published.",
    authorId: 2002,
    createdAt: "2026-09-15",
  },
  {
    noteId: "n-4",
    userId: 3103,
    roundId: 7,
    pairId: null,
    tag: null,
    body: "Called her. She says she will start next week.",
    authorId: 2001,
    createdAt: "2026-09-12",
  },
];

export const INITIAL_REQUESTS = [
  {
    requestId: 9001,
    action: "change_partner",
    roundId: 7,
    targetLabel: "Ma, Erin  ↔  Liu, Bob",
    participantId: "p-erin-7",
    pairId: 502,
    reason:
      "Mentee asked to change partner: schedules no longer overlap after her team move.",
    raisedBy: 2002,
    reviewerId: 2001,
    createdAt: "2026-09-22",
    status: "pending",
  },
  {
    requestId: 9002,
    action: "mark_no_show",
    roundId: 7,
    targetLabel: "Wu, Dana",
    participantId: "p-dana-7",
    pairId: null,
    reason:
      "Missed both mentor briefings and has not answered email or Teams since.",
    raisedBy: 2003,
    reviewerId: 2001,
    createdAt: "2026-09-21",
    status: "pending",
  },
];

/**
 * Every email in and out, one entry per message.
 *
 * They sit on the same timeline as the notes: "what happened with her" is one
 * question, and splitting it across two blocks makes the reader interleave
 * them by date in their head. Internal members are reminded on Teams, which
 * Purrf never sees, so for them the timeline holds only notes.
 */
export const INITIAL_EMAILS = [
  {
    messageId: "e-6",
    threadId: "t-gina-mt",
    userId: 3107,
    roundId: 7,
    direction: "out",
    templateKey: "mentorship_midterm_reminder",
    body: "You have logged 5 of 5 meetings for this round.",
    sentBy: 2001,
    at: "2026-09-18",
  },
  {
    messageId: "e-1",
    threadId: "t-cara-fc",
    userId: 3103,
    roundId: 7,
    direction: "out",
    templateKey: "mentorship_first_contact_reminder",
    body: "Our records show you have not yet contacted your mentor. The deadline is 2026-09-19.",
    sentBy: 2001,
    at: "2026-09-10",
  },
  {
    messageId: "e-2",
    threadId: "t-cara-fc",
    userId: 3103,
    roundId: 7,
    direction: "in",
    templateKey: "mentorship_first_contact_reminder",
    body: "Thanks — I have emailed Bob and copied the outreach address.",
    at: "2026-09-11",
  },
  {
    messageId: "e-3",
    threadId: "t-cara-mt",
    userId: 3103,
    roundId: 7,
    direction: "out",
    templateKey: "mentorship_midterm_reminder",
    body: "You have logged 0 of 5 meetings for this round. Please sign in to Purrf and record any meetings you have already held.",
    sentBy: 2001,
    at: "2026-09-18",
  },
  {
    messageId: "e-4",
    threadId: "t-alice-ob",
    userId: 3101,
    roundId: 7,
    direction: "out",
    templateKey: "mentorship_onboarding_reminder",
    body: "Your onboarding course is still open. It needs to be finished before matching.",
    sentBy: 2001,
    at: "2026-09-05",
    // Gmail refused it (quota). Pressed, not delivered.
    status: "failed",
  },
];

/**
 * Replies that are sitting in the mailbox but not yet pulled in.
 *
 * Pressing Refresh on the timeline brings them over — the manual fallback for
 * "I want to see it now, not when the push arrives".
 */
export const MAILBOX_REPLIES = [
  {
    messageId: "e-5",
    threadId: "t-cara-mt",
    userId: 3103,
    roundId: 7,
    direction: "in",
    templateKey: "mentorship_midterm_reminder",
    body: "Sorry — we met twice but I forgot to log it. Will do it tonight.",
    at: "2026-09-22",
  },
];

/** The actions that must be approved before they take effect. */
export const APPROVAL_ACTIONS = [
  { key: "withdraw", label: "Withdraw from round", target: "person" },
  { key: "mark_no_show", label: "Mark as no show", target: "person" },
  { key: "mark_red_flag", label: "Raise a red flag", target: "person" },
  { key: "change_partner", label: "Request a partner change", target: "pair" },
  { key: "revoke_flag", label: "Revoke a flag", target: "note" },
  {
    key: "publish_matching",
    label: "Publish matching results",
    target: "run",
  },
  {
    key: "exempt_matching",
    label: "Exempt from the history check",
    target: "person",
  },
  { key: "block_account", label: "Block from Purrf", target: "person" },
];

export const ACTION_LABELS = Object.fromEntries(
  APPROVAL_ACTIONS.map((a) => [a.key, a.label]),
);

/**
 * Feedback, as the participant wrote it.
 *
 * `partnerFeedback` sits on the row of the person who *wrote* it, which is why
 * the label everywhere reads "X's feedback about Y" and never "Pair feedback":
 * on Cara's page this is what Cara said, not what was said about her. Nobody
 * ever sees what their own partner wrote about them.
 */
export const INITIAL_FEEDBACK = {
  "p-dana-6": {
    programRating: 5,
    mostValuable: "Watching a mentee go from stuck to shipping.",
    challenges: "None worth mentioning.",
    partnerFeedback: [
      {
        partnerName: "Wang, Cara",
        rating: 5,
        text: "Came prepared to every session.",
      },
    ],
  },
  "p-cara-6": {
    programRating: 4,
    mostValuable:
      "Having someone outside my team to sanity-check career moves.",
    challenges: "Finding a slot that worked across time zones.",
    partnerFeedback: [
      {
        partnerName: "Wu, Dana",
        rating: 4,
        text: "Easy to talk to, though a few sessions got rescheduled late.",
      },
    ],
  },
};

/** The email templates the console can send. Wording is placeholder. */
export const EMAIL_TEMPLATES = [
  { key: "mentorship_round_recruitment", label: "New round invitation" },
  {
    key: "mentorship_onboarding_invite",
    label: "Admission & onboarding (resend)",
  },
  { key: "mentorship_onboarding_reminder", label: "Onboarding reminder" },
  { key: "mentorship_match_result_matched", label: "Match result — matched" },
  {
    key: "mentorship_match_result_unmatched",
    label: "Match result — not matched",
  },
  { key: "mentorship_first_contact_reminder", label: "First contact reminder" },
  { key: "mentorship_mentor_check_in", label: "Mentor check-in" },
  { key: "mentorship_midterm_reminder", label: "Mid-term reminder" },
  { key: "mentorship_final_followup", label: "Final follow-up" },
  { key: "mentorship_feedback_invite", label: "Feedback invitation" },
  { key: "mentorship_free_text", label: "Free text" },
];

export const TEMPLATE_LABELS = Object.fromEntries(
  EMAIL_TEMPLATES.map((t) => [t.key, t.label]),
);
