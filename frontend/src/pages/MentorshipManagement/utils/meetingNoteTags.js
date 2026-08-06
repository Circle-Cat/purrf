const ABSENT_TAGS = ["unknown_absent", "mentor_absent", "mentee_absent"];
const SPECIFIC_LATE_TAGS = ["mentor_late", "mentee_late"];
const ROLE_ABSENT_LATE_CONFLICTS = [
  ["mentor_absent", "mentor_late"],
  ["mentee_absent", "mentee_late"],
];

/**
 * Whether any absent tag is present in the given selection.
 *
 * @param {string[] | Set<string>} selectedTags - The currently selected tag identifiers.
 * @returns {boolean}
 */
export function hasAbsentTag(selectedTags) {
  const selected = new Set(selectedTags);
  return ABSENT_TAGS.some((tag) => selected.has(tag));
}

/**
 * Calculates which meeting note tags should be disabled based on the current selection.
 *
 * Enforces the following exclusivity rules:
 * 1. Mutually exclusive absent tags (selecting one absent tag disables all other absent tags).
 * 2. Mutually exclusive late tags (selecting "unknown_late" disables specific late tags, and vice versa).
 * 3. The same role cannot be marked as both absent and late.
 * 4. No absent tag can be selected while the meeting is marked Completed.
 *
 * @param {string[] | Set<string>} selectedTags - The currently selected tag identifiers.
 * @param {{isCompleted?: boolean}} [options]
 * @returns {Set<string>} A set of tag identifiers that should be disabled.
 */
export function getDisabledNoteTags(
  selectedTags,
  { isCompleted = false } = {},
) {
  const selected = new Set(selectedTags);
  const disabled = new Set();

  if (hasAbsentTag(selected)) {
    ABSENT_TAGS.forEach((tag) => {
      if (!selected.has(tag)) disabled.add(tag);
    });
  }

  if (isCompleted) {
    ABSENT_TAGS.forEach((tag) => disabled.add(tag));
  }

  if (selected.has("unknown_late")) {
    SPECIFIC_LATE_TAGS.forEach((tag) => disabled.add(tag));
  }
  if (SPECIFIC_LATE_TAGS.some((tag) => selected.has(tag))) {
    disabled.add("unknown_late");
  }

  ROLE_ABSENT_LATE_CONFLICTS.forEach(([absentTag, lateTag]) => {
    if (selected.has(absentTag)) disabled.add(lateTag);
    if (selected.has(lateTag)) disabled.add(absentTag);
  });

  return disabled;
}

/**
 * Maps a MeetingNoteTag to display text, substituting mentor/mentee names
 * for role-specific tags (absent/late).
 *
 * @param {string} tag - The MeetingNoteTag identifier.
 * @param {{mentorName: string, menteeName: string}} names
 * @returns {string} Display text for the tag.
 */
export function noteTagLabel(tag, { mentorName, menteeName }) {
  switch (tag) {
    case "mentor_absent":
      return `${mentorName} absent`;
    case "mentee_absent":
      return `${menteeName} absent`;
    case "mentor_late":
      return `${mentorName} late arrival`;
    case "mentee_late":
      return `${menteeName} late arrival`;
    case "unknown_absent":
      return "Unknown absence";
    case "unknown_late":
      return "Unknown late arrival";
    case "insufficient_duration":
      return "Insufficient duration";
    default:
      return tag;
  }
}
