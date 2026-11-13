/**
 * Every user-visible string on the mentorship banner. The wording is still
 * provisional, so it lives in one place: a copy change touches this file only.
 */
export const MENTORSHIP_BANNER_COPY = {
  fallbackTitle: "Mentorship",
  goalLabel: "Your goal:",
  steps: {
    register: "Register",
    training: "Training",
    matching: "Matching",
  },
  progressLabel: "Mentorship progress",
  narrowStep: (label, index, total) => `${label} · step ${index} of ${total}`,
  leadNext: "Next:",
  leadOverdue: "Overdue:",
  goToTraining: "Go to training",
  inDays: (days) =>
    days <= 0 ? "today" : days === 1 ? "in 1 day" : `in ${days} days`,
  nextRoundScheduled: (roundName, date) =>
    `registration for ${roundName} opens ${date}. We'll email you when it does.`,
  nextRoundUnscheduled:
    "register when the next round opens. We'll email you when it does.",
  registerBy: (date) => `register by ${date}.`,
  registerNoDate: "register for this round.",
  registerBySoon: (date, inDays) => `register by ${date} (${inDays}).`,
  registrationClosed: (roundName) =>
    `Registration for ${roundName} has closed. You can register when the next round opens. We'll email you when it does.`,
  trainingBy: (date) => `finish your onboarding training by ${date}.`,
  trainingNoDate: "finish your onboarding training.",
  trainingBySoon: (date, inDays) =>
    `finish your onboarding training by ${date} (${inDays}).`,
  trainingOverdue: (dueDate, matchDate) =>
    matchDate
      ? `your onboarding training was due ${dueDate}. Finish it before matches are made on ${matchDate}, or you can't be matched this round.`
      : `your onboarding training was due ${dueDate}. Finish it before matches are made, or you can't be matched this round.`,
  matchesAnnouncedOn: (date) => `matches are announced ${date}.`,
  matchesAnnouncedSoon: "matches will be announced soon.",
  matched:
    "see who you're matched with. Your meetings for this round are in Mentorship Participation below.",
  unmatched:
    "You weren't matched this round. You may still be matched with someone this round if a partner is available. You can register again when the next round opens.",
  pairingEnded: (roundName) =>
    `Your pairing for ${roundName} has ended. You can register again when the next round opens.`,
  pairingEndedMayRematch: (roundName) =>
    `Your pairing for ${roundName} has ended. You may be matched with someone new this round if a partner is available. Otherwise, you can register again when the next round opens.`,
  participationEnded: (roundName) =>
    `Your participation in ${roundName} has ended. You can register again when the next round opens.`,
  notTakingPart: (roundName) =>
    `You aren't taking part in ${roundName}. You can register again when the next round opens.`,
  withdrawn: (roundName) =>
    `You've withdrawn from ${roundName}. You can register again when the next round opens.`,
  resultNotReady: (roundName) =>
    `Your match result for ${roundName} isn't ready yet. Contact the mentorship team if you have questions.`,
  profileLine:
    "Before each round, check that your profile is up to date. We use your education and work history to find your match.",
  updateProfile: "Update profile →",
};
