/**
 * Placeholder rounds, people, pairs and notes for the mentorship admin prototype.
 *
 * This bundle is published to a public URL, so every name, address, reason and
 * feedback quote here is invented. The set is chosen to cover each combination
 * the console has to render rather than to look like a realistic roster:
 *
 *   - a mentor carrying two mentees (one row on the person axis, two on pairs)
 *   - all four states of "meetings last round": first time, unmatched, 0, n/m
 *   - a pair that has made first contact and one that has not
 *   - an ended pair, so `inactive` renders somewhere
 *   - someone admitted but not yet registered, so the Non-participants tab
 *     has a row
 *   - notes of all three kinds: written, decided-by-approval, system
 */

/** The admin the prototype signs you in as. */
export const CURRENT_USER = { userId: 2001, name: "Jiang, Goose" };

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
    requiredMeetings: 5,
    status: "active",
    timeline: {
      promotionStartAt: "2026-08-18",
      mentorApplicationDeadlineAt: "2026-08-25",
      menteeApplicationDeadlineAt: "2026-08-25",
      onboardingNotificationAt: "2026-09-02",
      onboardingDeadlineAt: "2026-09-09",
      matchNotificationAt: "2026-09-12",
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
 * `lastRound` carries the four-state value deliberately as an object rather
 * than a number, because "never took part", "was not matched", "matched and
 * held none" and "3 of 5" are four different answers and only one of them is
 * the number zero.
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
    lastRound: { kind: "first-time" },
    midtermReminderAt: null,
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
    onboardingDone: true,
    lastRound: { kind: "count", completed: 5, required: 5 },
    midtermReminderAt: null,
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
    lastRound: { kind: "count", completed: 0, required: 5 },
    midtermReminderAt: "2026-09-18",
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
    onboardingDone: false,
    lastRound: { kind: "unmatched" },
    midtermReminderAt: null,
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
    lastRound: { kind: "first-time" },
    midtermReminderAt: null,
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
    onboardingDone: true,
    lastRound: { kind: "count", completed: 4, required: 5 },
    midtermReminderAt: "2026-09-18",
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
    lastRound: { kind: "count", completed: 5, required: 5 },
    midtermReminderAt: "2026-09-18",
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
    lastRound: { kind: "first-time" },
    midtermReminderAt: "2025-07-02",
  },
];

/**
 * People with an onboarding training row but no participant row for the round.
 *
 * They are not filtered out of the Participants tab — they were never in it.
 * "Who still has to register" is a question only this tab can answer.
 */
export const NON_PARTICIPANTS = [
  {
    userId: 3108,
    roundId: 7,
    name: "Osei, Kwame",
    email: "kwame@example.com",
    identity: "external",
    mentorOnboarding: null,
    menteeOnboarding: "in_progress",
  },
  {
    userId: 3109,
    roundId: 7,
    name: "Rossi, Lia",
    email: "lia@circlecat.org",
    identity: "internal",
    mentorOnboarding: "done",
    menteeOnboarding: null,
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
];

export const INITIAL_MEETINGS = [
  {
    meetingId: "m-1",
    pairId: 502,
    date: "2026-09-14",
    start: "10:00",
    end: "11:00",
    completed: true,
    tags: [],
  },
  {
    meetingId: "m-2",
    pairId: 502,
    date: "2026-09-07",
    start: "10:00",
    end: "10:20",
    completed: true,
    tags: ["insufficient_duration"],
  },
  {
    meetingId: "m-3",
    pairId: 502,
    date: "2026-08-30",
    start: "10:00",
    end: "11:00",
    completed: false,
    tags: ["mentee_absent"],
  },
  {
    meetingId: "m-4",
    pairId: 503,
    date: "2026-09-10",
    start: "09:00",
    end: "10:00",
    completed: true,
    tags: [],
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
  status_change: "system",
  onboarding_reminder: "recorded",
  first_contact_reminder: "recorded",
  mentor_check_in: "recorded",
  midterm_reminder: "recorded",
  final_followup: "recorded",
};

export const NOTE_LABELS = {
  no_show: "No show",
  red_flag: "Red flag",
  partner_change_request: "Partner change request",
  status_change: "Status change",
  onboarding_reminder: "Onboarding reminder",
  first_contact_reminder: "First contact reminder",
  mentor_check_in: "Mentor check-in",
  midterm_reminder: "Mid-term reminder",
  final_followup: "Final follow-up",
};

/** Tags an admin may write directly. The rest go through an approval. */
export const RECORDED_TAGS = Object.keys(NOTE_KIND).filter(
  (tag) => NOTE_KIND[tag] === "recorded",
);

export const INITIAL_NOTES = [
  {
    noteId: "n-1",
    participantId: "p-cara-7",
    pairId: null,
    tag: "no_show",
    body: "No response after the first-contact deadline. Email and Teams both tried.",
    authorId: 2002,
    createdAt: "2026-09-20",
  },
  {
    noteId: "n-2",
    participantId: "p-cara-7",
    pairId: null,
    tag: "midterm_reminder",
    body: "Sent on Teams. No reply yet.",
    authorId: 2001,
    createdAt: "2026-09-18",
  },
  {
    noteId: "n-3",
    participantId: "p-cara-7",
    pairId: null,
    tag: "status_change",
    body: "signed_up → matched. Raised by Jiang, Goose. Approved by Wang, Jasmine.",
    authorId: 2002,
    createdAt: "2026-09-15",
  },
  {
    noteId: "n-4",
    participantId: "p-cara-7",
    pairId: null,
    tag: null,
    body: "Called her. She says she will start next week.",
    authorId: 2001,
    createdAt: "2026-09-12",
  },
  {
    noteId: "n-5",
    participantId: "p-erin-7",
    pairId: 502,
    tag: "partner_change_request",
    body: "Mentee asked to change partner: schedules no longer overlap after her team move.",
    authorId: 2001,
    createdAt: "2026-09-20",
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
    raisedBy: 2001,
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
      "Five days past the first-contact deadline. No reply on email or Teams.",
    raisedBy: 2001,
    createdAt: "2026-09-21",
    status: "pending",
  },
];

/** The actions that must be approved before they take effect. */
export const APPROVAL_ACTIONS = [
  { key: "withdraw", label: "Withdraw from round" },
  { key: "mark_no_show", label: "Mark as no show" },
  { key: "mark_red_flag", label: "Raise a red flag" },
  { key: "change_partner", label: "Request a partner change" },
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
  { key: "mentorship_onboarding_invite", label: "Onboarding invitation" },
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

export const MEETING_TAG_LABELS = {
  insufficient_duration: "Too short",
  unknown_absent: "Someone absent",
  mentor_absent: "Mentor absent",
  mentee_absent: "Mentee absent",
  unknown_late: "Someone late",
  mentor_late: "Mentor late",
  mentee_late: "Mentee late",
};
