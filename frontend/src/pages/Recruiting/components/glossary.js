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
    hint: "This application was closed and the applicant is blocked from future postings and from using Purrf at all.",
  },
  "evaluation.no_longer_assigned": {
    label: "No longer assigned",
    hint: "This session was reassigned to someone else, so it is read-only for you.",
  },
  // Written for the recruiter, not the candidate: these buttons decide
  // someone else's edit access, and nothing else on the page says so.
  "application.edit_lock": {
    label: "Status",
    hint: "Moving off Pending closes the application to the candidate's own edits, as do advancing the stage and confirming an evaluation. It is one-way — setting the status back to Pending does not give their edit access back.",
  },
  "posting.draft": {
    label: "Draft",
    hint: "Not published yet, and only you can see it. Edit it as much as you like, then submit it for review when it is ready.",
  },
  "posting.draft_in_review": {
    label: "Draft",
    hint: "Still unpublished. It keeps the Draft badge while its review is open, which is why you cannot edit it right now.",
  },
  "posting.published": {
    label: "Published",
    hint: "Live and accepting applications.",
  },
  "posting.closed": {
    label: "Closed",
    hint: "Not accepting applications. Reopen it if it was ever published, or delete it if it never was.",
  },
  "posting.pending_review": {
    label: "Pending review",
    hint: "Waiting on a reviewer's approve or reject decision. Nothing can be edited meanwhile.",
  },
  "posting.revision_pending_review": {
    label: "Revision pending review",
    hint: "An edit to this live posting is awaiting review. What's live stays live and keeps accepting applications.",
  },
  "posting.pending_close": {
    label: "Pending close",
    hint: "A close request is awaiting review. The posting stays published until it is approved.",
  },
  "posting.pending_reopen": {
    label: "Pending reopen",
    hint: "A reopen request is awaiting review. The posting stays closed until it is approved.",
  },
  "reject.initial": {
    label: "Initial submission rejected",
    hint: "The reviewer sent this back instead of publishing it, and it is a Draft again. Their comment is in the panel below.",
  },
  "reject.revision": {
    label: "Revision rejected",
    hint: "The reviewer rejected a staged edit. What's live is untouched and the edit is kept, so you can resubmit or discard it.",
  },
  "reject.close": {
    label: "Close request rejected",
    hint: "The reviewer rejected a close request, so the posting stays published exactly as it was.",
  },
  "reject.reopen": {
    label: "Reopen request rejected",
    hint: "The reviewer rejected a reopen request, so the posting stays closed exactly as it was.",
  },
  "reject.unknown": {
    label: "Sent back",
    hint: "A reviewer sent this back. Their comment is in the panel below.",
  },
  "tag.cold_freeze": {
    label: "Cold freeze",
    hint: "This applicant is reapplying inside the posting's cooldown window. It does not block them — it is here for your judgement.",
  },
  "tag.blacklisted": {
    label: "Blacklisted",
    hint: "This applicant is currently blocked from every posting and from using Purrf at all. The tag can appear even if nobody was blacklisted from this posting, because blacklisting sweeps every posting the person has applied to.",
  },
  "tag.blacklist_lifted": {
    label: "Blacklist Lifted",
    hint: "This applicant was blacklisted and has since been unblocked, so they are not blocked now.",
  },
  "review.initial": {
    label: "Initial Request",
    hint: "First submission of a draft for publication. Rejecting sends it back to Draft.",
  },
  "review.revision": {
    label: "Revision Request",
    hint: "An edit to an already-published posting. Rejecting leaves it published and keeps the edit, so the author can resubmit or discard it.",
  },
  "review.close": {
    label: "Close Request",
    hint: "A request to close a published posting. Rejecting just aborts the request.",
  },
  "review.reopen": {
    label: "Reopen Request",
    hint: "A request to reopen a closed posting. Rejecting just aborts the request. If the posting carries a staged edit, approving republishes that proposed version rather than the one that was live before it closed.",
  },
  "posting.staged_edit": {
    label: "Editing a live posting",
    hint: "Saving stages your change without touching what applicants see. The posting stays published on its current version, you can keep re-editing the staged copy, and it only goes live once a reviewer approves it.",
  },
  "posting.undeletable": {
    label: "Cannot be deleted",
    hint: "A posting that has ever been published can never be deleted, whatever its current status. Close it instead; only a draft, or a closed posting that was never published, can be deleted.",
  },
  "board.lanes": {
    label: "How the lanes read",
    hint: "One lane per pipeline stage, with multi-session stages split into Session 1, Session 2 and so on, then the terminal lanes. Employment postings end with Offer, Hired and Rejected; activity postings have no Offer lane and label the success lane Admitted.",
  },
  "editor.basics": {
    label: "Basics",
    hint: "Title, description, posting type, an optional mentorship role, and a cooldown before a rejected applicant may re-apply. Posting type and mentorship role lock once the posting is published.",
  },
  "editor.application_form": {
    label: "Application form",
    hint: "The questions applicants answer -- short or long text, single or multi choice, or exact-match text.",
  },
  "editor.pipeline": {
    label: "Interview pipeline",
    hint: "Pick one or more recruiters -- staff who can advance applicants through every stage of this posting -- then add the stages applicants move through, in order. A stage can require several sessions.",
  },
  "editor.screening": {
    label: "Machine screening",
    hint: "Optional conditions checked the moment an applicant applies, matched against their answers or their verified email domain. Each can reject them, or hire them outright with no human review.",
  },
  "editor.profile": {
    label: "Profile requirements",
    hint: "Whether education, work experience and resume are Required, Optional or Off for applicants.",
  },
};

/**
 * A term's explanation as a plain string, for the places a `TermHint` cannot
 * go. The board's applicant card is one clickable `<button>`, so a tooltip
 * trigger inside it would nest a control in a control and steal the click the
 * card exists to receive; a `title` attribute is an attribute, not an element,
 * and does neither. Same copy, weaker affordance, used only where structure
 * rules the component out.
 *
 * @param {string} id A glossary id.
 * @returns {string|undefined} The hint, or undefined for an unknown id.
 */
export const termHint = (id) => GLOSSARY[id]?.hint;

/**
 * Lock reasons, mirroring `ApplicationLockReason` in
 * `backend/common/recruiting_enums.py`. Held to that enum by
 * `tests/shared/application_lock_reasons.json`.
 */
export const APPLICATION_LOCK_REASONS = ["advanced", "in_review", "closed"];

/**
 * What to tell a candidate about why their application is closed to edits.
 *
 * The wording lives here rather than on the backend because the ADVANCED
 * sentence names a stage, and stage labels live in this glossary. The
 * IN_REVIEW sentence deliberately says only that work has begun: the backend
 * collapses a moved sub-status and a frozen submission into one reason,
 * because telling them apart would publish internal mechanics that change
 * nothing the reader can do. CLOSED is about the posting rather than the
 * application: it stopped taking submissions, so there is nothing to edit
 * into it.
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
  if (reason === "closed") {
    return "This posting has closed, so it can't be edited any more.";
  }
  return null;
};

/**
 * Resolves a rejected review's kind to a glossary id, falling back for a kind
 * this frontend does not know yet (a backend-added JobReviewKind).
 *
 * @param {string | null | undefined} kind The `lastRejectKind` from JobDto.
 * @returns {string} A glossary id that always resolves.
 */
export const rejectTermId = (kind) =>
  GLOSSARY[`reject.${kind}`] ? `reject.${kind}` : "reject.unknown";

/**
 * Resolves a JobReviewKind to its glossary id, or null for a kind this
 * frontend does not know yet, so the caller can fall back to the raw value
 * rather than render nothing.
 *
 * @param {string} kind A JobReviewKind value.
 * @returns {string|null}
 */
export const reviewTermId = (kind) =>
  GLOSSARY[`review.${kind}`] ? `review.${kind}` : null;

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
