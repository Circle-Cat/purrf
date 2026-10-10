export const STAGE_OPTIONS = [
  { value: "round_recruitment", label: "New round invitation" },
  { value: "admission", label: "Admission & onboarding" },
  { value: "onboarding_reminder", label: "Onboarding reminder" },
  { value: "match_result", label: "Match result" },
  { value: "first_contact_reminder", label: "First contact reminder" },
  { value: "mentor_check_in", label: "Mentor check-in" },
  { value: "midterm_reminder", label: "Mid-term reminder" },
  { value: "final_followup", label: "Final follow-up" },
  { value: "feedback_invite", label: "Feedback invitation" },
];

export const stageLabel = (value) =>
  STAGE_OPTIONS.find((o) => o.value === value)?.label ?? value;

export const NOTIFICATION_STATES = [
  { value: "not_notified", label: "Not notified" },
  { value: "scheduled", label: "Scheduled" },
  { value: "notified", label: "Notified" },
];

export const notificationStateLabel = (value) =>
  NOTIFICATION_STATES.find((o) => o.value === value)?.label ?? value;

// What can reach someone not registered for the round; the invitation is
// only for them.
const NOT_REGISTERED_STAGES = [
  "round_recruitment",
  "admission",
  "onboarding_reminder",
];

/** The stages the Participants filter offers for one list. */
export const stagesForList = (notRegistered) =>
  STAGE_OPTIONS.filter((o) =>
    notRegistered
      ? NOT_REGISTERED_STAGES.includes(o.value)
      : o.value !== "round_recruitment",
  );
