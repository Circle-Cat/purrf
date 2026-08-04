/**
 * Role-specific workflow copy for the recruiting "How it works" dialogs.
 * Kept as plain data so it can be edited and tested independently of the
 * presentational HowItWorksDialog component.
 */

/** Author-facing guide for the Postings page. */
export const POSTINGS_GUIDE = {
  title: "How postings work",
  description: "The lifecycle of a job posting, from draft to closed.",
  steps: [
    {
      title: "Create a draft",
      detail:
        'Use "New posting" to start. It saves as a draft that only you can see.',
    },
    {
      title: "Build the posting",
      detail:
        "Edit the application form, pipeline stages, screening rules, and profile config.",
    },
    {
      title: "Submit for review",
      detail:
        'Pick a reviewer and add an optional message. The posting needs at least one pipeline stage and one owner ("Managed by") before it can be submitted; once submitted it moves to pending review.',
    },
    {
      title: "Get a decision",
      detail:
        "On approval the posting is published and live to candidates. On rejection it returns to draft with the reviewer's comment.",
    },
    {
      title: "Revise a published posting",
      detail:
        "Editing a live posting stages the change without touching what's live — the posting stays Published, and you can keep re-editing the staged draft as many times as you like before you're ready.",
    },
    {
      title: "Submit or discard the staged edit",
      detail:
        "Submit it for review (same reviewer picker as a new posting) or use Discard draft to drop it and leave the live posting untouched. Once submitted, the Operate actions disappear until the reviewer decides.",
    },
    {
      title: "If a revision is rejected",
      detail:
        "The staged edit is kept, not discarded — the posting stays published and you can resubmit the same change or discard it from there.",
    },
    {
      title: "Close or reopen",
      detail:
        "Request to close a published posting, or request to reopen a closed one. Both need approval.",
    },
  ],
  statuses: [
    {
      name: "Draft",
      description:
        "Editable, visible only to you. Submit for review to publish.",
    },
    {
      name: "Pending review",
      description: "Waiting on a reviewer's approve or reject decision.",
    },
    { name: "Published", description: "Live and accepting applications." },
    {
      name: "Revision pending review",
      description: "An edit to a live posting is awaiting review.",
    },
    {
      name: "Pending close",
      description: "A close request is awaiting review.",
    },
    {
      name: "Pending reopen",
      description: "A reopen request is awaiting review.",
    },
    {
      name: "Closed",
      description:
        "Not accepting applications. Reopen if it was published, or delete if it never was.",
    },
  ],
  notes: [
    "You cannot review your own posting.",
    "Only a posting that was never published can be deleted.",
  ],
};

/** Author-facing guide for the New/Edit posting form. */
export const POSTING_EDITOR_GUIDE = {
  title: "How posting setup works",
  description: "What each part of this form does.",
  steps: [
    {
      title: "Basics",
      detail:
        "Title, description, kind, optional mentorship role, and a cooldown before a rejected applicant can re-apply. Kind and mentorship role lock once the posting is published.",
    },
    {
      title: "Application form",
      detail:
        "Add the questions applicants answer — short/long text, single/multi choice, or exact-match text.",
    },
    {
      title: "Interview pipeline",
      detail:
        "Pick one or more owners who can advance applicants, then add stages in the order applicants move through them.",
    },
    {
      title: "Screening rules",
      detail:
        "Optional conditions checked the moment an applicant applies, matched against their answers or their verified email domain. Each rule can reject, qualify (let them through like an unscreened applicant), or auto-hire (send them straight to Hired with no human review).",
    },
    {
      title: "Profile requirements",
      detail:
        "Choose whether education, work experience, and resume are required, optional, or off for applicants.",
    },
    {
      title: "Save",
      detail:
        "Saving never publishes by itself — it creates or updates a draft (or stages an edit to a live posting). Submit it for review separately from the posting's detail page when it's ready.",
    },
  ],
  statusesTitle: "Key concepts",
  statuses: [
    {
      name: "Managed by",
      description:
        "Staff who can advance applicants through every stage of this posting's pipeline.",
    },
    {
      name: "Stage",
      description:
        "One step of the interview pipeline, e.g. recruiter screening or tech; each can require multiple rounds.",
    },
    {
      name: "Screen rule",
      description:
        "An automatic condition checked against an applicant's answers or verified email domain when they apply — it can reject, qualify, or auto-hire them.",
    },
    {
      name: "Profile requirement",
      description:
        "Whether education, work experience, and resume are Required, Optional, or Off for applicants.",
    },
  ],
  notes: [
    "Kind and mentorship role can only be changed while the posting is a draft.",
    'Submitting for review needs at least one pipeline stage and one owner ("Managed by").',
    "The live preview on the right updates as you edit.",
  ],
};

/** Reviewer-facing guide for the My reviews page. */
export const REVIEWS_GUIDE = {
  title: "How reviews work",
  description: "How to act on postings submitted for your approval.",
  steps: [
    {
      title: "Check your queue",
      detail: "This page lists postings waiting on your approval.",
    },
    {
      title: "Open a review",
      detail:
        "Inspect the posting details, pipeline, and form schema. Revisions, and reopen requests with a staged edit, show the live and pending versions side by side.",
    },
    {
      title: "Approve",
      detail:
        "Approving advances the posting — publishing, revising, closing, or reopening it as requested. Approving a reopen that carries a staged edit republishes the proposed version, not the old one.",
    },
    {
      title: "Reject",
      detail:
        "Always requires a comment. An Initial Request sends the posting back to Draft; a Revision Request leaves it published with the staged edit kept, not discarded, so the author can resubmit or discard it; Close and Reopen Requests just abort, leaving the posting exactly as it was.",
    },
  ],
  statuses: [
    {
      name: "Initial Request",
      description: "First submission of a draft for publication.",
    },
    {
      name: "Revision Request",
      description: "An edit to an already-published posting.",
    },
    {
      name: "Close Request",
      description: "A request to close a published posting.",
    },
    {
      name: "Reopen Request",
      description: "A request to reopen a closed posting.",
    },
  ],
  notes: [
    "A comment is required when you reject.",
    "You cannot review your own submissions.",
    "You're notified when a posting is submitted to you, and the author is notified of your decision.",
    "The posting's Review history tab records every review decision.",
  ],
};

/** Owner-facing guide for the Applications Board. */
export const APPLICATIONS_BOARD_GUIDE = {
  title: "How the board works",
  description: "Track applicants through your posting's interview pipeline.",
  steps: [
    {
      title: "Pick a posting",
      detail:
        "Switch between postings using the dropdown next to the title — the postings you own, or every posting if you have read-all access.",
    },
    {
      title: "Read the lanes",
      detail:
        'Each lane is one pipeline stage (multi-round stages split into Round 1, Round 2, ...), followed by the terminal lanes. Employment postings end with Offer, Hired, and Rejected; activity postings have no Offer lane and label the success lane "Admitted" instead of "Hired".',
    },
    {
      title: "Open an applicant",
      detail:
        "Click any card to see their full application, evaluations, and take action.",
    },
  ],
  notes: [
    'A "Cold freeze" tag means this applicant is reapplying within the posting\'s cooldown window.',
    '"Blacklisted" vs "Blacklist Lifted" distinguishes a currently-blocked applicant from one who was blacklisted but has since been unblocked.',
    "A blacklist chip can appear even if no one was blacklisted from this posting — blacklisting sweeps every posting the person has applied to.",
  ],
};

/** Owner/read.all-facing guide for the application detail page's operate panel. */
export const APPLICATION_OWNER_GUIDE = {
  title: "How application review works",
  description: "Move an applicant through the pipeline and record decisions.",
  steps: [
    {
      title: "Check status",
      detail:
        "Sub-status buttons under the stage badge track where the applicant is within the current stage.",
    },
    {
      title: "Advance",
      detail:
        "Moves the applicant to the next stage (or next round, if the stage has more than one). If the current round has no confirmed evaluation yet, you're asked to confirm before advancing. Interview stages let you pick an assignee, or leave it for later.",
    },
    {
      title: "Reassign",
      detail:
        "Change who's currently responsible for this stage — always requires picking someone.",
    },
    {
      title: "Reject or Blacklist",
      detail:
        "Reject ends this application with a reason. Blacklist rejects this application, blocks the applicant from every future posting, and also closes out all of their other applications everywhere — including any already Hired — tagging each as blacklisted.",
    },
    {
      title: "Review evaluations",
      detail:
        "The Evaluations tab shows every submitted scorecard; Timeline shows the full history; Comments lets you discuss with other staff.",
    },
  ],
  notes: [
    "Scheduling an interview stage requires an assignee first.",
    'The "Evaluated" sub-status can only be set once a confirmed evaluation exists for the current round.',
    "Blacklisting needs the blacklist permission; without it the button is disabled.",
    "read.all viewers see this same panel read-only — they can't act on it.",
  ],
};

/** Evaluator-facing guide for the application detail page's rubric view (?mode=evaluate). */
export const APPLICATION_EVALUATOR_GUIDE = {
  title: "How evaluating works",
  description: "Score this candidate's current interview stage.",
  steps: [
    {
      title: "Fill out the rubric",
      detail:
        "Fields are Pass/Fail, a 1-5 score, or a notes-only field for free-form comments (some Pass/Fail and score fields also take notes).",
    },
    {
      title: "Save draft",
      detail:
        "Keeps your progress without submitting — you can come back and change it.",
    },
    {
      title: "Confirm & Submit",
      detail: "Locks your evaluation. It can't be edited after this.",
    },
    {
      title: "Comments",
      detail:
        "Discuss the candidate with the owner or other staff — separate from your score.",
    },
  ],
  notes: [
    "If you've been reassigned away from this stage, you'll see a message instead of the form.",
    "You can expand the candidate's other and previous applications for this posting to see their snapshot and past evaluation scores — the audit timeline and comments there stay hidden from evaluators.",
  ],
};
