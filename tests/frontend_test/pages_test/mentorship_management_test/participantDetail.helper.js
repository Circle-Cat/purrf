// Values that a swapped read would expose are deliberately distinct: the
// person (3104) and partner (22) ids, the two rounds (7 and 3), the two
// note authors (9 and 12).
export const pairOf = (overrides = {}) => ({
  pairId: 80,
  partner: {
    id: 22,
    firstName: "Bob",
    lastName: "Smith",
    preferredName: null,
    isActive: true,
  },
  completedMeetingCount: 2,
  attendanceIssues: [],
  firstMeetingAt: "2026-09-02T17:00:00Z",
  ...overrides,
});

export const registrationOf = (overrides = {}) => ({
  userId: 3104,
  firstName: "Alice",
  lastName: "Chen",
  preferredName: null,
  primaryEmail: "alice@x.com",
  alternativeEmails: [],
  isBlocked: false,
  isDeactivated: false,
  isInternal: true,
  roundId: 7,
  roundName: "Fall 2026",
  participantRole: "mentee",
  approvalStatus: "matched",
  mentorOnboardingStatus: null,
  menteeOnboardingStatus: "done",
  pairs: [pairOf()],
  requiredMeetings: 5,
  exemptionFindings: [],
  exemptionRequest: null,
  ...overrides,
});

export const noteOf = (overrides = {}) => ({
  noteId: 501,
  tag: null,
  body: "Asked to move the first meeting.",
  pairId: null,
  requestId: null,
  author: { userId: 9, name: "Dana Wu" },
  createdAt: "2026-09-03T18:00:00Z",
  ...overrides,
});

export const detailOf = (overrides = {}) => ({
  person: {
    userId: 3104,
    firstName: "Alice",
    lastName: "Chen",
    preferredName: null,
    primaryEmail: "alice@x.com",
    alternativeEmails: [],
    isBlocked: false,
    isDeactivated: false,
    isInternal: true,
  },
  round: { roundId: 7, name: "Fall 2026", requiredMeetings: 5, inProgress: true },
  registration: registrationOf(),
  exempted: false,
  feedback: null,
  notes: [],
  pendingBlockRequest: null,
  history: [],
  ...overrides,
});
