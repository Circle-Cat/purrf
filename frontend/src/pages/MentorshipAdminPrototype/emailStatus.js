/**
 * The notifications of a round, in the order they go out, and how to tell
 * whether each one has reached a given person.
 *
 * A notification counts however it went: an email from Purrf, or anything
 * else — Teams, Google Chat, a call — recorded by hand as a note. So nothing
 * here is stored. "Notified" is read from what already exists: an email on the
 * person's timeline with one of the step's templates; for the admission email,
 * the notification Purrf sent on its own when they were admitted; or a
 * recorded note with the step's tag, written when an admin marks it notified.
 * Every step has a tag, so every one can be marked by hand.
 */
export const EMAIL_STEPS = [
  {
    key: "round_recruitment",
    label: "New round invitation",
    short: "Invitation",
    templates: ["mentorship_round_recruitment"],
    tag: "round_invitation",
    registered: false,
  },
  {
    // Sent by Purrf itself the moment someone is admitted, mentor or mentee,
    // and it carries the onboarding course and its deadline. The template is
    // only for sending it again by hand.
    key: "admission",
    label: "Admission & onboarding",
    short: "Admission",
    templates: ["mentorship_onboarding_invite"],
    tag: "admission_notice",
    automatic: "mentorship_admitted",
    registered: null,
  },
  {
    key: "onboarding_reminder",
    label: "Onboarding reminder",
    short: "Onboarding reminder",
    templates: ["mentorship_onboarding_reminder"],
    tag: "onboarding_reminder",
    registered: null,
  },
  {
    key: "match_result",
    label: "Match result",
    short: "Match result",
    templates: [
      "mentorship_match_result_matched",
      "mentorship_match_result_unmatched",
    ],
    tag: "match_result_notice",
    registered: true,
  },
  {
    key: "first_contact_reminder",
    label: "First contact reminder",
    short: "First contact",
    templates: ["mentorship_first_contact_reminder"],
    tag: "first_contact_reminder",
    registered: true,
  },
  {
    key: "mentor_check_in",
    label: "Mentor check-in",
    short: "Mentor check-in",
    templates: ["mentorship_mentor_check_in"],
    tag: "mentor_check_in",
    registered: true,
  },
  {
    key: "midterm_reminder",
    label: "Mid-term reminder",
    short: "Mid-term",
    templates: ["mentorship_midterm_reminder"],
    tag: "midterm_reminder",
    registered: true,
  },
  {
    key: "final_followup",
    label: "Final follow-up",
    short: "Final follow-up",
    templates: ["mentorship_final_followup"],
    tag: "final_followup",
    registered: true,
  },
  {
    key: "feedback_invite",
    label: "Feedback invitation",
    short: "Feedback",
    templates: ["mentorship_feedback_invite"],
    tag: "feedback_invite",
    registered: true,
  },
];

/** The steps shown for a registered person, or for someone not registered. */
export const stepsFor = (registered) =>
  EMAIL_STEPS.filter(
    (s) => s.registered === null || s.registered === registered,
  );

/** In the order a notification moves through them. */
export const EMAIL_STATES = [
  { key: "not_sent", label: "Not notified" },
  { key: "sent", label: "Notified" },
  { key: "failed", label: "Failed" },
  { key: "replied", label: "Replied" },
];

/**
 * Where one step stands for one person in one round.
 *
 * A reply outranks a plain send; a successful send outranks an earlier
 * failure, so a retried message reads as sent. A failure with nothing after
 * it stays visible — it was pressed, and it did not arrive.
 *
 * @returns {{state: string, channel?: string, at?: string}}
 */
export const stepState = (
  step,
  { userId, roundId },
  emails,
  notes,
  notifications = [],
) => {
  const mine = emails.filter(
    (e) =>
      e.userId === userId &&
      e.roundId === roundId &&
      step.templates.includes(e.templateKey),
  );
  const out = mine.filter((e) => e.direction === "out");
  const delivered = out.filter((e) => e.status !== "failed");
  const reply = mine.find(
    (e) =>
      e.direction === "in" && delivered.some((o) => o.threadId === e.threadId),
  );
  if (reply) return { state: "replied", channel: "email", at: reply.at };
  const latest = (list) =>
    [...list].sort((a, b) => b.at.localeCompare(a.at))[0];
  if (delivered.length) {
    return { state: "sent", channel: "email", at: latest(delivered).at };
  }
  const automatic = step.automatic
    ? notifications.filter(
        (n) =>
          n.userId === userId &&
          n.roundId === roundId &&
          n.event === step.automatic,
      )
    : [];
  const autoSent = automatic.filter((n) => n.status === "delivered");
  if (autoSent.length) {
    return { state: "sent", channel: "auto", at: latest(autoSent).at };
  }
  const marked = step.tag
    ? notes.filter(
        (n) =>
          n.userId === userId && n.roundId === roundId && n.tag === step.tag,
      )
    : [];
  if (marked.length) {
    return { state: "sent", channel: "manual", at: latest(marked).createdAt };
  }
  if (out.length)
    return { state: "failed", channel: "email", at: latest(out).at };
  if (automatic.length) {
    return { state: "failed", channel: "auto", at: latest(automatic).at };
  }
  return { state: "not_sent" };
};
