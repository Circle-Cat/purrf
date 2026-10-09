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
