/**
 * Pure helpers shared by the player page and the page that hosts it.
 *
 * Nothing here touches the DOM or window, so the rules that decide what a
 * course sees can be tested without an iframe.
 */

export const MESSAGE_TYPES = {
  // The player announces itself once its script has run, because the page
  // that hosts it cannot tell from the outside when that happened.
  READY: "scorm:ready",
  INIT: "scorm:init",
  SAVED: "scorm:saved",
  COMMIT: "scorm:commit",
  FINISH: "scorm:finish",
  ERROR: "scorm:error",
};

const MESSAGE_TYPE_VALUES = new Set(Object.values(MESSAGE_TYPES));

/**
 * Whether a course has been here before.
 *
 * scorm-again does not derive this, and courses that read it branch on it.
 * @param {{suspendData?: string|null}} progress
 * @returns {"resume"|"ab-initio"}
 */
export const deriveEntry = (progress) =>
  progress?.suspendData ? "resume" : "ab-initio";

/**
 * Seconds as the SCORM 1.2 CMITimespan a course expects in total_time.
 * @param {number} seconds
 * @returns {string} HHHH:MM:SS
 */
const toTimespan = (seconds) => {
  const whole = Math.max(0, Math.floor(seconds || 0));
  const pad = (n) => String(n).padStart(2, "0");
  return `${pad(Math.floor(whole / 3600))}:${pad(
    Math.floor((whole % 3600) / 60),
  )}:${pad(whole % 60)}`;
};

/**
 * The CMI model to seed before the course frame exists.
 * @param {object} progress Stored progress, or {} for a fresh assignment.
 * @param {{userId: number, displayName: string}} learner
 * @returns {Object<string, string>} Flattened CMI for loadFromFlattenedJSON.
 */
export const toFlattenedCmi = (progress = {}, learner) => ({
  "cmi.core.student_id": String(learner.userId),
  "cmi.core.student_name": learner.displayName,
  "cmi.core.credit": "credit",
  "cmi.core.lesson_mode": "normal",
  "cmi.core.entry": deriveEntry(progress),
  "cmi.core.total_time": toTimespan(progress.sessionTimeSeconds),
  "cmi.core.lesson_status": progress.lessonStatus || "not attempted",
  "cmi.core.lesson_location": progress.lessonLocation || "",
  "cmi.suspend_data": progress.suspendData || "",
  "cmi.launch_data": "",
});

/**
 * Whether a postMessage event is one of ours, from where we expect.
 *
 * The origin check is the whole security of the bridge: without it any page
 * could post a completed course through it.
 * @param {MessageEvent} event
 * @param {string} expectedOrigin
 * @returns {boolean}
 */
export const isTrustedMessage = (event, expectedOrigin) =>
  event?.origin === expectedOrigin &&
  !!event.data &&
  typeof event.data === "object" &&
  MESSAGE_TYPE_VALUES.has(event.data.type);
