/**
 * The single source for every recruiting term shown to a user, and the
 * resolver that maps an application stage to one. `TermHint` renders these;
 * nothing else should hold a user-facing definition of a recruiting concept.
 */

/**
 * Application stages, mirroring `ApplicationStage` in
 * `backend/common/recruiting_enums.py`. Held to that enum by
 * `tests/shared/application_stages.json`, which
 * `application_stages_vector_test.py` pins from the other side.
 */
export const APPLICATION_STAGES = [
  "applied",
  "recruiter_screening",
  "behavioral",
  "tech",
  "board_review",
  "offer",
  "hired",
  "rejected",
  "blacklisted",
];

/**
 * Every term a user can be shown, keyed by glossary id. A stage's hint is
 * written for the candidate, who reads it on their own application, so it
 * answers "is anything expected of me" before anything else.
 */
export const GLOSSARY = {
  "stage.applied": {
    label: "Applied",
    hint: "Your application is in. Nothing is needed from you right now.",
  },
  "stage.recruiter_screening": {
    label: "Recruiter screening",
    hint: "A recruiter is reviewing your application. Nothing is needed from you right now.",
  },
  "stage.behavioral": {
    label: "Behavioral",
    hint: "A behavioral interview round. Your interviewer will be in touch to arrange a time.",
  },
  "stage.tech": {
    label: "Tech",
    hint: "A technical interview round. Your interviewer will be in touch to arrange a time.",
  },
  "stage.board_review": {
    label: "Board review",
    hint: "Your completed interviews are being reviewed together before a decision.",
  },
  "stage.offer": {
    label: "Offer",
    hint: "An offer is being prepared. A recruiter will be in touch.",
  },
  "stage.hired": {
    label: "Hired",
    hint: "You were hired for this posting.",
  },
  "stage.admitted": {
    label: "Admitted",
    hint: "You were admitted to this activity.",
  },
  "stage.rejected": {
    label: "Rejected",
    hint: "This application did not move forward.",
  },
  "stage.blacklisted": {
    label: "Blacklisted",
    hint: "This application was closed and the applicant is blocked from future postings.",
  },
  "evaluation.no_longer_assigned": {
    label: "No longer assigned",
    hint: "This session was reassigned to someone else, so it is read-only for you.",
  },
  "posting.draft": {
    label: "Draft",
    hint: "Not yet published. A posting keeps its Draft badge while a review is open — that's why you can't edit it right now.",
  },
};

/**
 * Lock reasons, mirroring `ApplicationLockReason` in
 * `backend/common/recruiting_enums.py`. Held to that enum by
 * `tests/shared/application_lock_reasons.json`.
 */
export const APPLICATION_LOCK_REASONS = ["advanced", "in_review"];

/**
 * What to tell a candidate about why their application is closed to edits.
 *
 * The wording lives here rather than on the backend because the ADVANCED
 * sentence names a stage, and stage labels live in this glossary. The
 * IN_REVIEW sentence deliberately says only that work has begun: the backend
 * collapses a moved sub-status and a frozen submission into one reason,
 * because telling them apart would publish internal mechanics that change
 * nothing the reader can do.
 *
 * @param {string|null|undefined} reason An `ApplicationLockReason` value.
 * @param {string|null|undefined} stageLabel The stage's human label, when known.
 * @returns {string|null} The sentence to show, or null when nothing is locked.
 */
export const lockReasonText = (reason, stageLabel) => {
  if (reason === "advanced") {
    return stageLabel
      ? `It moved to ${stageLabel}, so it can't be edited any more.`
      : "It moved on, so it can't be edited any more.";
  }
  if (reason === "in_review") {
    return "A recruiter has started reviewing it, so it can't be edited any more.";
  }
  return null;
};

/**
 * Resolves an application stage to its glossary id. Activity postings have no
 * offer step and present a hired applicant as "Admitted".
 *
 * @param {string} stage An `ApplicationStage` value.
 * @param {string|null|undefined} jobKind A `JobKind` value ("employment" | "activity").
 * @returns {string|null} The glossary id, or null when the stage is unknown.
 */
export const stageTermId = (stage, jobKind) => {
  if (!APPLICATION_STAGES.includes(stage)) return null;
  if (jobKind === "activity" && stage === "hired") return "stage.admitted";
  return `stage.${stage}`;
};
