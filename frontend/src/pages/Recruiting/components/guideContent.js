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
        "Pick a reviewer and add an optional message. The posting moves to pending review.",
    },
    {
      title: "Get a decision",
      detail:
        "On approval the posting is published and live to candidates. On rejection it returns to draft with the reviewer's comment.",
    },
    {
      title: "Revise a published posting",
      detail:
        "Editing a live posting parks it in published pending revision — resubmit the change for review.",
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
    "At least 2 active approvers must exist before you can submit for review.",
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
        "Optional conditions that auto-reject an applicant based on their answers as soon as they apply.",
    },
    {
      title: "Profile requirements",
      detail:
        "Choose whether education, work experience, and resume are required, optional, or off for applicants.",
    },
    {
      title: "Save",
      detail:
        "Saving never publishes by itself — it creates or updates a draft (or stages an edit to a live posting). Submit it for review separately from the Postings page when it's ready.",
    },
  ],
  statusesTitle: "Key concepts",
  statuses: [
    {
      name: "Owner(s)",
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
        "An automatic reject condition checked against an applicant's answers when they apply.",
    },
    {
      name: "Profile requirement",
      description:
        "Whether education, work experience, and resume are Required, Optional, or Off for applicants.",
    },
  ],
  notes: [
    "Kind and mentorship role can only be changed while the posting is a draft.",
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
        "Approving advances the posting — publishing, revising, closing, or reopening it as requested.",
    },
    {
      title: "Reject",
      detail:
        "Rejecting sends the posting back to its author. A comment is required.",
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
  ],
};
