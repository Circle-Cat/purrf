/**
 * Utility functions for the Round create/edit modal.
 *
 * Timezone rule: all dates are expressed as 23:59:59 Pacific Time (America/Los_Angeles),
 * converted to UTC before sending to the backend.
 */
import { TZDate } from "@date-fns/tz";
import { localToUtcIso } from "@/utils/dateTime";

/**
 * Single source of truth for the mentorship round timeline.
 *
 * Drives PhaseTimelineTable rendering and all form logic in this file
 * (validation, EMPTY_FORM, mapRoundToForm, buildUpsertPayload).
 *
 * Field metadata:
 *   key      – camelCase key used in form state and the backend timeline object
 *   label    – human-readable label shown in the UI and in validation messages
 *   required – whether the field is required in the round form
 */
export const TIMELINE_PHASES = [
  {
    phase: "Sign-up",
    dotColor: "bg-sky-500",
    adminAction: {
      key: "promotionStartAt",
      label: "Date to send recruitment email",
      required: true,
    },
    participantDeadlines: [
      {
        key: "mentorApplicationDeadlineAt",
        label: "Mentor application deadline",
        required: true,
      },
      {
        key: "menteeApplicationDeadlineAt",
        label: "Mentee application deadline",
        required: true,
      },
    ],
  },
  {
    phase: "Onboarding",
    dotColor: "bg-violet-500",
    adminAction: {
      key: "trainingNotificationAt",
      label: "Date to send onboarding email",
      required: false,
    },
    participantDeadlines: [
      {
        key: "trainingDeadlineAt",
        label: "Completion deadline",
        required: false,
      },
    ],
  },
  {
    phase: "Matching",
    dotColor: "bg-emerald-500",
    adminAction: {
      key: "matchNotificationAt",
      label: "Date to publish matching email",
      required: true,
    },
    participantDeadlines: [
      {
        key: "matchingCompletedAt",
        label: "First contact with mentor",
        required: false,
      },
    ],
  },
  {
    phase: "Reminder",
    dotColor: "bg-amber-500",
    adminAction: {
      key: "meetingLogReminderAt",
      label: "Mid-term reminder email",
      required: false,
    },
    participantDeadlines: [
      {
        key: "meetingsCompletionDeadlineAt",
        label: "Complete required meetings",
        required: true,
      },
    ],
  },
  {
    phase: "Feedback",
    dotColor: "bg-rose-500",
    adminAction: {
      key: "feedbackStartAt",
      label: "Send feedback email",
      required: false,
    },
    participantDeadlines: [
      {
        key: "feedbackDeadlineAt",
        label: "Feedback submission deadline",
        required: false,
      },
    ],
  },
];

/** Flattened list of all timeline fields in phase order (admin first, then participants). */
export const FLATTENED_TIMELINE_FIELDS = TIMELINE_PHASES.flatMap(
  ({ adminAction, participantDeadlines }) => [
    adminAction,
    ...participantDeadlines,
  ],
);

/** Maps field keys to "[Phase] [Column]" labels for grid-aligned error messages. */
export const FIELD_LABEL_MAP = TIMELINE_PHASES.reduce(
  (labelMap, { phase, adminAction, participantDeadlines }) => {
    labelMap[adminAction.key] = `${phase} Admin Action`;
    participantDeadlines.forEach((f) => {
      labelMap[f.key] = `${phase} Participant Deadline`;
    });
    return labelMap;
  },
  {},
);

/**
 * Convert a Date object to a UTC ISO-8601 string representing 23:59:59 on
 * that date in Pacific Time (America/Los_Angeles).
 *
 * @param {Date|null} date
 * @returns {string|null} UTC ISO string, e.g. "2025-12-19T07:59:59Z"
 */
export function toPTEndOfDay(date) {
  if (!date) return null;
  return localToUtcIso(date, "23:59:59", "America/Los_Angeles");
}

/**
 * Convert a UTC ISO-8601 string to a plain Date at local midnight, where the
 * date components (year/month/day) match the calendar date in America/Los_Angeles.
 * Returns null for null/undefined.
 *
 * @param {string|null} isoStr
 * @returns {Date|null}
 */
export function fromUTCToPTDate(isoStr) {
  if (!isoStr) return null;
  const pt = new TZDate(new Date(isoStr), "America/Los_Angeles");
  return new Date(pt.getFullYear(), pt.getMonth(), pt.getDate());
}

/**
 * Return the default timeline dates and requiredMeetings for a given season
 * and year. All dates are plain Date objects (local midnight).
 *
 * Spring uses year Y for most dates but Y-1 for promotionStartAt and the
 * application deadlines (sign-up happens before the new year).
 *
 * @param {"Spring"|"Summer"|"Fall"} season
 * @param {number} year
 * @returns {Object|null} form-shaped defaults, or null for unknown season
 */
export function getSeasonDefaults(season, year) {
  const y = Number(year);

  if (season === "Spring") {
    return {
      requiredMeetings: 5,
      promotionStartAt: new Date(y - 1, 11, 18),
      mentorApplicationDeadlineAt: new Date(y - 1, 11, 25),
      menteeApplicationDeadlineAt: new Date(y - 1, 11, 25),
      trainingNotificationAt: new Date(y, 1, 2),
      trainingDeadlineAt: new Date(y, 1, 9),
      matchNotificationAt: new Date(y, 1, 12),
      matchingCompletedAt: new Date(y, 1, 26),
      meetingLogReminderAt: new Date(y, 3, 2),
      meetingsCompletionDeadlineAt: new Date(y, 3, 30),
      feedbackStartAt: new Date(y, 4, 2),
      feedbackDeadlineAt: new Date(y, 4, 9),
    };
  }

  if (season === "Summer") {
    return {
      requiredMeetings: 7,
      promotionStartAt: new Date(y, 3, 18),
      mentorApplicationDeadlineAt: new Date(y, 3, 25),
      menteeApplicationDeadlineAt: new Date(y, 3, 25),
      trainingNotificationAt: new Date(y, 4, 2),
      trainingDeadlineAt: new Date(y, 4, 9),
      matchNotificationAt: new Date(y, 4, 12),
      matchingCompletedAt: new Date(y, 4, 26),
      meetingLogReminderAt: new Date(y, 6, 2),
      meetingsCompletionDeadlineAt: new Date(y, 7, 31),
      feedbackStartAt: new Date(y, 8, 2),
      feedbackDeadlineAt: new Date(y, 8, 9),
    };
  }

  if (season === "Fall") {
    return {
      requiredMeetings: 5,
      promotionStartAt: new Date(y, 7, 18),
      mentorApplicationDeadlineAt: new Date(y, 7, 25),
      menteeApplicationDeadlineAt: new Date(y, 7, 25),
      trainingNotificationAt: new Date(y, 8, 2),
      trainingDeadlineAt: new Date(y, 8, 9),
      matchNotificationAt: new Date(y, 8, 12),
      matchingCompletedAt: new Date(y, 8, 26),
      meetingLogReminderAt: new Date(y, 10, 2),
      meetingsCompletionDeadlineAt: new Date(y, 10, 30),
      feedbackStartAt: new Date(y, 11, 2),
      feedbackDeadlineAt: new Date(y, 11, 9),
    };
  }

  return null;
}

/** Empty form state used when creating a new round. */
export const EMPTY_FORM = {
  id: null,
  name: "",
  requiredMeetings: 0,
  ...Object.fromEntries(
    FLATTENED_TIMELINE_FIELDS.map(({ key }) => [key, null]),
  ),
};

/**
 * Map an API round object to the flat form state expected by RoundModal.
 *
 * @param {Object} round – API response shape
 * @returns {Object} form state
 */
export function mapRoundToForm(round) {
  const tl = round.timeline ?? {};
  return {
    id: round.id,
    name: round.name ?? "",
    requiredMeetings: round.requiredMeetings ?? 5,
    ...Object.fromEntries(
      FLATTENED_TIMELINE_FIELDS.map(({ key }) => [
        key,
        fromUTCToPTDate(tl[key]),
      ]),
    ),
  };
}

/**
 * Build the RoundsCreateDto payload from the form state, converting Pacific Time date
 * strings to UTC ISO strings.  Pass null for optional fields that are empty.
 *
 * @param {Object} form
 * @returns {Object} API-ready payload
 */
export function buildUpsertPayload(form) {
  return {
    ...(form.id != null && { id: form.id }),
    name: form.name.trim(),
    required_meetings: Number(form.requiredMeetings),
    timeline: Object.fromEntries(
      FLATTENED_TIMELINE_FIELDS.map(({ key }) => [
        key,
        toPTEndOfDay(form[key]),
      ]),
    ),
  };
}

export function validateForm(form, existingNames = []) {
  const name = form.name.trim();
  if (!name) return { name: "This field is required." };
  const duplicate = existingNames.find(
    (n) => n.toLowerCase() === name.toLowerCase(),
  );
  if (duplicate) return { name: `Round "${duplicate}" already exists.` };
  if (form.requiredMeetings == null)
    return { requiredMeetings: "This field is required." };
  const meetings = Number(form.requiredMeetings);
  if (meetings < 0 || meetings > 10)
    return { requiredMeetings: "Must be between 0 and 10." };

  let minDate = { date: null, key: "" };

  for (const { adminAction, participantDeadlines } of TIMELINE_PHASES) {
    const adminDate = form[adminAction.key];
    if (!adminDate && adminAction.required)
      return { [adminAction.key]: "This field is required." };
    if (adminDate && minDate.date && adminDate <= minDate.date)
      return {
        [adminAction.key]: `Must be after ${FIELD_LABEL_MAP[minDate.key]}.`,
      };

    const participantMinDate = adminDate
      ? { date: adminDate, key: adminAction.key }
      : minDate;
    let phaseEnd = { ...participantMinDate };

    for (const field of participantDeadlines) {
      const date = form[field.key];
      if (!date && field.required)
        return { [field.key]: "This field is required." };
      if (date && participantMinDate.date && date <= participantMinDate.date)
        return {
          [field.key]: `Must be after ${FIELD_LABEL_MAP[participantMinDate.key]}.`,
        };
      if (date && date > phaseEnd.date) phaseEnd = { date, key: field.key };
    }

    minDate = phaseEnd;
  }

  return {};
}
