/**
 * Every email Purrf sends from content written in code, as of main on
 * 2026-09-30.
 *
 * Manual templates are copied verbatim from
 * `backend/communication/email_templates.py`, placeholders included — the
 * preview fills those in. Automatic notification bodies are each renderer's
 * output for one invented event, following the shape of the copy functions
 * they call. Every person and address in the sample data is made up and uses
 * an example domain.
 */

export const SERVICES = [
  { key: "recruiting", label: "Recruiting" },
  { key: "mentorship", label: "Mentorship" },
  { key: "users", label: "Users" },
];

/** Sender alias per service. Users mail has no alias of its own yet. */
export const SENDERS = {
  recruiting: { address: "recruiting@circlecat.org", tbd: false },
  mentorship: { address: "mentorship@circlecat.org", tbd: false },
  users: { address: "notifications@circlecat.org", tbd: true },
};

/** Values the preview uses for the auto-filled `{{...}}` placeholders. */
export const SAMPLE_VALUES = {
  candidate_name: "Jordan Rivera",
  position_title: "Backend Engineer",
  sender_name: "Morgan Lee",
};

/** What each auto-filled placeholder is filled with in the product. */
export const PLACEHOLDER_INFO = {
  candidate_name: "The applicant's legal first and last name",
  position_title: "The title of the posting they applied to",
  sender_name: "The staff member sending the email",
};

const SIGNATURE =
  "<p>Best,<br><strong>{{sender_name}}</strong><br>" +
  "Director of People Operations<br>Circle Cat Inc</p>";

const ONBOARDING_FORM_URL =
  "https://docs.google.com/forms/d/e/" +
  "1FAIpQLSdlc-oaOg6I2Cj3jDgV66qeHzEcy0_AmWT8n_-urAucFV3hvA/viewform";

const manual = (key, name, subject, body) => ({
  key,
  name,
  service: "recruiting",
  mode: "manual",
  variants: [{ label: null, subject, body }],
});

export const MANUAL_TEMPLATES = [
  manual(
    "screening_passed_cultural_invite",
    "Screening passed - request behavioral interview availability",
    "Circle Cat Program - Interview Availability",
    "<p>Dear {{candidate_name}},</p>" +
      "<p>I received your application from a colleague for {{position_title}} and we're " +
      "definitely interested in speaking with you! Our typical interview process consists of a round " +
      "of cultural and value interview and a round of technical interview (if you are applying for " +
      "Software or Course design role) with individuals from different teams. Let me know if you have " +
      "any questions in the meantime!</p>" +
      "<p><strong>What's next?</strong></p>" +
      "<p>Before we can schedule your interview, please provide your availability for a 45-minute " +
      "cultural and value phone interview. We can schedule the interview from 9PM to 4AM ET. Please " +
      "provide 5-6 dates/times over the next 1-2 weeks that will work for your schedule.</p>" +
      "<p><strong>Accommodations</strong></p>" +
      "<p>It's important to us to create an accessible, inclusive workplace for everyone, so please do " +
      "not hesitate to contact me if you need any accommodations for your interviews. We will then " +
      "connect with you to confidentially discuss your options.</p>" +
      "<p><strong>What equipment will I need?</strong></p>" +
      "<p>You'll need a computer with internet access.<br>" +
      "This interview will take place over the Google Meet.</p>" +
      "<p>In the meantime, please let me know if you have any questions.</p>" +
      SIGNATURE,
  ),
  manual(
    "cultural_interview_scheduled",
    "Behavioral interview scheduled",
    "Your Circle Cat Behavioral Interview is Scheduled",
    "<p>Dear {{candidate_name}},</p>" +
      "<p>Thank you for your patience while we sort things out. We are looking forward to speaking with " +
      "you! Your interview has been scheduled for [INTERVIEW DATE/TIME].</p>" +
      "<p>You will receive a Google Meet invitation in a separate email shortly. Please accept that " +
      "invite to confirm your attendance and to ensure the link is saved to your calendar.</p>" +
      "<p>This round of interview is similar to a traditional behavioral round interview, where you can " +
      "expect questions about your past experiences, work style, etc.</p>" +
      "<p>If you need any accommodations or a schedule adjustment, please reply to this email and let us " +
      "know. We're happy to help.</p>" +
      SIGNATURE,
  ),
  manual(
    "interview_rescheduled",
    "Interview rescheduled",
    "Your Circle Cat Interview — Updated Time",
    "<p>Dear {{candidate_name}},</p>" +
      "<p>Your interview has been rescheduled to [INTERVIEW DATE/TIME].</p>" +
      SIGNATURE,
  ),
  manual(
    "cultural_passed_technical_invite",
    "Behavioral passed - request technical interview availability",
    "Circle Cat — Technical Interview Availability",
    "<p>Dear {{candidate_name}},</p>" +
      "<p>Congratulations! You did a great job on your behavioral interview and we would like to move " +
      "you to the next step in the interview process.</p>" +
      "<p><strong>What's next?</strong></p>" +
      "<p>The next steps will consist of scheduling and prepping for your interview. Please provide your " +
      "availability for a 45-minute technical phone interview. We can schedule the interview from 9PM " +
      "to 4AM ET. Please provide 5-6 dates/times over the next 1-2 weeks that will work for your " +
      "schedule.</p>" +
      "<p><strong>Prep materials</strong></p>" +
      "<p>The most popular prep websites are below:</p>" +
      "<ul>" +
      "<li>GeeksForGeeks.org</li>" +
      "<li>Leetcode.com</li>" +
      "<li>Topcoder.com</li>" +
      '<li>"Cracking the Coding Interview" (a book that every engineer recommends on our teams!)</li>' +
      "</ul>" +
      "<p>I would work on problems that make you break down an issue, design the most efficient answer, " +
      'code cleanly, then check your work - typically these are "parking lot" type problems and ' +
      '"lottery" problems. These problems will be designed to push you to the limit, so more than ' +
      "finding the perfect answer, you will need to produce the most efficient answer and be able to " +
      "justify your method and explain it to the interviewer. It is the approach you take to solving a " +
      "problem in our interviews that determines your performance, rather than what you do or do not " +
      "know. Also, writing solutions out by hand would be beneficial because you will be expected to " +
      "do so on a google doc during yourinterview.</p>" +
      "<p><strong>Accommodations</strong></p>" +
      "<p>It's important to us to create an accessible, inclusive workplace for everyone, so please do " +
      "not hesitate to contact me if you need any accommodations for your interviews. We will then " +
      "connect with you to confidentially discuss your options.</p>" +
      "<p><strong>What equipment will I need?</strong></p>" +
      "<p>You'll need a computer with internet access for the interviews to use Google Docs — a " +
      "web-based word processor which lets you share and collaborate your work online. Note: You will " +
      "not have access to an editor or compiler.<br>" +
      "This interview will take place over Google Meet. We recommend using a headset or hands-free " +
      "device during the interview, to allow for easier conversation while coding.</p>" +
      "<p>If you have any questions or concerns, please don't hesitate to reach out. Best of luck during " +
      "your interview.<br>" +
      "Thanks!</p>" +
      SIGNATURE,
  ),
  manual(
    "technical_interview_scheduled",
    "Technical interview scheduled",
    "Your Circle Cat Technical Interview is Scheduled",
    "<p>Dear {{candidate_name}},</p>" +
      "<p>We are looking forward to speaking with you! Your technical interview has been scheduled for " +
      "[INTERVIEW DATE/TIME].</p>" +
      "<p>You will receive a Google Meet invitation in a separate email shortly. Please accept that " +
      "invite to confirm your attendance and to ensure the link is saved to your calendar.</p>" +
      "<p>If you need any accommodations or a schedule adjustment, please reply to this email and let us " +
      "know. We're happy to help.</p>" +
      SIGNATURE,
  ),
  manual(
    "feedback_complete_ask_start_date",
    "Feedback complete - ask for start date",
    "Circle Cat — Next Steps",
    "<p>Dear {{candidate_name}},</p>" +
      "<p>We have received all feedback from your interview. Can you let us know when you want your " +
      "start date to be?</p>" +
      SIGNATURE,
  ),
  manual(
    "offer_onboarding",
    "Offer and onboarding",
    "Welcome to Circle Cat — Onboarding & Next Steps",
    "<p>Dear {{candidate_name}},</p>" +
      "<p>It is a pleasure talking to you and our team is excited to have you " +
      "onboard! If you wish to proceed with " +
      "循环猫实习计划志愿者/实习生" +
      "(Residency Program Volunteer/Trainee), please fill out " +
      `<a href="${ONBOARDING_FORM_URL}">this form</a>` +
      " and we will grant you access to our corp resources.</p>" +
      "<p>Your role is: [SOFTWARE ENGINEER VOLUNTEER / SOFTWARE ENGINEER INTERN]<br>" +
      "Your manager will be: [MANAGER NAME] [MANAGER EMAIL]<br>" +
      "Your start date: [START DATE]</p>" +
      "<p>Once you have filled out the form, there will be a couple of things " +
      "coming up:</p>" +
      "<p><strong>Onboard to corp resources</strong></p>" +
      "<p>You will be given credentials and instructions to onboard corp " +
      "resources in 1-2 business days after you have filled out the form. " +
      "Follow those instructions and make sure you have access to accounts " +
      "needed for work.</p>" +
      "<p>If you need employer information for immigration purposes, you can " +
      "visit circlecat.org/about or send me an email directly so I can help " +
      "you fill out forms required by the DSO or the USCIS.</p>" +
      "<p>Please let me know if you have any questions or if I can provide any " +
      "additional information.</p>" +
      SIGNATURE,
  ),
  manual(
    "rejection",
    "Rejection",
    "Your Application to Circle Cat",
    "<p>Dear {{candidate_name}},</p>" +
      "<p>I would like to thank you for taking the time to discuss your interests with " +
      "{{position_title}} with us. I regret to inform you that we have decided not to " +
      "progress further with your application.</p>" +
      "<p>We wish you every success with your future endeavor and thank you for your interest in " +
      "Circle Cat.</p>" +
      SIGNATURE,
  ),
];

// Sample event data for the automatic previews.
const CANDIDATE = "Jordan Rivera";
const CANDIDATE_LINE = `<p>Candidate: ${CANDIDATE} (jordan.rivera@example.com)</p>`;
const JOB = "Backend Engineer";
const ACTOR = "Alex Chen";
const R_FOOTER =
  "<p>This is an automated message from Purrf. Replies to this address " +
  "aren't monitored.</p>";
const M_FOOTER =
  "<p>This is an automated message from Purrf. Please do not reply " +
  "directly to this email as this inbox is not monitored.</p>";

const OWNERS = "Owners of the posting";
const OWNERS_AND_ASSIGNEES =
  "Owners of the posting and whoever is assigned to the application now";

/**
 * `recipients` never includes whoever caused the event: the pipeline drops the
 * actor from every recipient set before sending.
 */
const recruiting = ({
  key,
  name,
  trigger,
  recipients,
  unverified,
  variants,
}) => ({
  key,
  name,
  service: "recruiting",
  mode: "automatic",
  trigger,
  recipients,
  unverified: unverified ?? {},
  variants: variants.map((v) => ({ ...v, body: v.body + R_FOOTER })),
});

export const AUTOMATIC_TEMPLATES = [
  recruiting({
    key: "recruiting.application_submitted",
    name: "New application",
    trigger:
      "When someone submits an application — including one a screening rule hires (or, on an activity posting, admits) outright",
    recipients: OWNERS,
    variants: [
      {
        label: "Submitted",
        subject: `New application: ${CANDIDATE} for ${JOB}`,
        body:
          `<p>${CANDIDATE} applied to ${JOB}. The application is waiting for review at the Recruiter screening stage.</p>` +
          CANDIDATE_LINE +
          "<p>You're receiving this because you own this posting. Open the Applications Board in Purrf to review it.</p>",
      },
      {
        label: "Auto-hired by a screening rule",
        subject: `Application auto-hired: ${CANDIDATE} (${JOB})`,
        body:
          `<p>${CANDIDATE} applied to ${JOB} and was hired automatically, with no human review.</p>` +
          CANDIDATE_LINE +
          "<p>The matching screening rule is recorded on the application's timeline in Purrf.</p>",
      },
    ],
  }),
  recruiting({
    key: "recruiting.auto_rejected",
    name: "Application auto-rejected",
    trigger: "When a screening rule rejects an application as it is submitted",
    recipients: OWNERS,
    variants: [
      {
        label: null,
        subject: `Application auto-rejected: ${CANDIDATE} (${JOB})`,
        body:
          `<p>${CANDIDATE} applied to ${JOB} and was rejected automatically, with no human review.</p>` +
          CANDIDATE_LINE +
          "<p>The reason is recorded on the application's timeline in Purrf. No action is needed unless you want to overturn it.</p>",
      },
    ],
  }),
  recruiting({
    key: "recruiting.reassigned · recruiting.auto_assigned",
    name: "Evaluation assigned",
    trigger:
      "When someone assigns an evaluator (directly, or by moving the application into an interview stage), or when a stage's default assignee is applied automatically",
    recipients:
      "Assigned by someone: owners of the posting and the current assignee. Applied automatically: the current assignee only",
    variants: [
      {
        label: "Assigned by a colleague",
        subject: `Evaluation assigned: ${CANDIDATE} (${JOB})`,
        body:
          `<p>${ACTOR} assigned you to evaluate ${CANDIDATE} for ${JOB}.</p>` +
          CANDIDATE_LINE +
          "<p>Stage: Tech, session 2.</p>" +
          "<p>Open My Interview Evaluations in Purrf to submit your evaluation.</p>",
      },
      {
        label: "Default assignee, automatic",
        subject: `Evaluation assigned: ${CANDIDATE} (${JOB})`,
        body:
          `<p>You were automatically assigned to evaluate ${CANDIDATE} for ${JOB}, as the posting's default assignee for this stage.</p>` +
          CANDIDATE_LINE +
          "<p>Stage: Behavioral.</p>" +
          "<p>Open My Interview Evaluations in Purrf to submit your evaluation.</p>",
      },
    ],
  }),
  recruiting({
    key: "recruiting.mentioned",
    name: "Mentioned in a comment",
    trigger:
      "When someone @-mentions a colleague in a comment on an application",
    recipients: "The colleagues mentioned in the comment",
    variants: [
      {
        label: null,
        subject: `${ACTOR} mentioned you: ${CANDIDATE} (${JOB})`,
        body:
          `<p>${ACTOR} mentioned you in a comment on ${CANDIDATE}'s application for ${JOB}.</p>` +
          CANDIDATE_LINE +
          "<p>Open the application in Purrf and go to its Comments tab to read the thread and reply.</p>",
      },
    ],
  }),
  recruiting({
    key: "recruiting.review_opened",
    name: "Posting review requested",
    trigger: "When someone submits a job posting for review",
    recipients: "The reviewer named on the review",
    variants: [
      {
        label: null,
        subject: `Posting review requested: ${JOB}`,
        body:
          `<p>${ACTOR} submitted the posting "${JOB}" for your review. It is waiting on your decision.</p>` +
          "<p>Open My Posting Reviews in Purrf to approve or reject it.</p>",
      },
    ],
  }),
  recruiting({
    key: "recruiting.review_reassigned",
    name: "Posting review reassigned",
    trigger:
      "When the submitter moves a pending posting review to a different reviewer",
    recipients: "The new reviewer (the previous reviewer isn't told)",
    variants: [
      {
        label: null,
        subject: `Posting review reassigned: ${JOB}`,
        body:
          `<p>${ACTOR} moved the review of the posting "${JOB}" to you. It is waiting on your decision.</p>` +
          "<p>Open My Posting Reviews in Purrf to approve or reject it.</p>",
      },
    ],
  }),
  recruiting({
    key: "recruiting.review_decided",
    name: "Posting review decided",
    trigger: "When the reviewer approves or rejects a job posting",
    recipients: "Whoever submitted the posting for review",
    variants: [
      {
        label: "Approved",
        subject: `Posting approved: ${JOB}`,
        body:
          `<p>${ACTOR} approved your submission for the posting "${JOB}".</p>` +
          "<p>Open Job Postings in Purrf to see its current state.</p>",
      },
      {
        label: "Rejected",
        subject: `Posting rejected: ${JOB}`,
        body:
          `<p>${ACTOR} rejected your submission for the posting "${JOB}".</p>` +
          "<p>Open Job Postings in Purrf to see the outcome and any comment the reviewer left.</p>",
      },
    ],
  }),
  recruiting({
    key: "recruiting.blacklisted",
    name: "Application blacklisted",
    trigger:
      "When a person is blocked and their applications are closed out — one email per application",
    recipients: OWNERS,
    variants: [
      {
        label: null,
        subject: `Application blacklisted: ${CANDIDATE} (${JOB})`,
        body:
          `<p>${ACTOR} blacklisted ${CANDIDATE} and rejected their application for ${JOB}, with the reason: "Did not attend two scheduled interviews".</p>` +
          CANDIDATE_LINE,
      },
    ],
  }),
  recruiting({
    key: "recruiting.stage_changed",
    name: "Stage changed",
    trigger: "When someone moves an application to a different stage",
    recipients: OWNERS_AND_ASSIGNEES,
    variants: [
      {
        label: null,
        subject: `Stage changed: ${CANDIDATE} (${JOB})`,
        body:
          `<p>${ACTOR} moved ${CANDIDATE}'s application for ${JOB} to the Tech stage.</p>` +
          CANDIDATE_LINE +
          "<p>Open the Applications Board in Purrf to see it.</p>",
      },
    ],
  }),
  recruiting({
    key: "recruiting.round_advanced",
    name: "Round advanced",
    trigger:
      "When someone advances an application to its next interview round within the same stage",
    recipients: OWNERS_AND_ASSIGNEES,
    unverified: { trigger: true },
    variants: [
      {
        label: null,
        subject: `Round advanced: ${CANDIDATE} (${JOB})`,
        body:
          `<p>${ACTOR} advanced ${CANDIDATE}'s Tech round for ${JOB} to round 2.</p>` +
          CANDIDATE_LINE +
          "<p>Open the Applications Board in Purrf to see it.</p>",
      },
    ],
  }),
  recruiting({
    key: "recruiting.sub_status_changed",
    name: "Status changed",
    trigger:
      "When someone changes an application's status within its stage (for example Pending to Scheduling)",
    recipients: OWNERS,
    variants: [
      {
        label: null,
        subject: `Status changed: ${CANDIDATE} (${JOB})`,
        body:
          `<p>${ACTOR} moved ${CANDIDATE}'s Behavioral status for ${JOB} to Scheduling.</p>` +
          CANDIDATE_LINE +
          "<p>Open the Applications Board in Purrf to see it.</p>",
      },
    ],
  }),
  recruiting({
    key: "recruiting.evaluation_confirmed",
    name: "Evaluation submitted",
    trigger: "When an evaluator submits their evaluation of an application",
    recipients: OWNERS,
    variants: [
      {
        label: null,
        subject: `Evaluation submitted: ${CANDIDATE} (${JOB})`,
        body:
          `<p>${ACTOR} submitted their evaluation of ${CANDIDATE} for ${JOB}.</p>` +
          CANDIDATE_LINE +
          "<p>Stage: Behavioral.</p>" +
          "<p>Open the Applications Board in Purrf to read it.</p>",
      },
    ],
  }),
  recruiting({
    key: "recruiting.interview_scheduled",
    name: "Interview scheduled",
    trigger: "When someone schedules an interview on an application",
    recipients: OWNERS_AND_ASSIGNEES,
    variants: [
      {
        label: null,
        subject: `Interview scheduled: ${CANDIDATE} (${JOB})`,
        body:
          `<p>${ACTOR} scheduled an interview with ${CANDIDATE} for ${JOB}, on 2026-10-08 01:00 UTC.</p>` +
          CANDIDATE_LINE +
          "<p>Stage: Behavioral.</p>" +
          "<p>Open the Applications Board in Purrf to see it.</p>",
      },
    ],
  }),
  recruiting({
    key: "recruiting.interview_updated",
    name: "Interview rescheduled",
    trigger: "When someone changes the time of a scheduled interview",
    recipients: OWNERS_AND_ASSIGNEES,
    variants: [
      {
        label: null,
        subject: `Interview rescheduled: ${CANDIDATE} (${JOB})`,
        body:
          `<p>${ACTOR} rescheduled ${CANDIDATE}'s interview for ${JOB} to 2026-10-09 02:30 UTC.</p>` +
          CANDIDATE_LINE +
          "<p>Stage: Behavioral.</p>" +
          "<p>Open the Applications Board in Purrf to see it.</p>",
      },
    ],
  }),
  recruiting({
    key: "recruiting.interview_cancelled",
    name: "Interview cancelled",
    trigger: "When someone cancels a scheduled interview",
    recipients: OWNERS_AND_ASSIGNEES,
    variants: [
      {
        label: null,
        subject: `Interview cancelled: ${CANDIDATE} (${JOB})`,
        body:
          `<p>${ACTOR} cancelled ${CANDIDATE}'s interview for ${JOB}, which was set for 2026-10-08 01:00 UTC.</p>` +
          CANDIDATE_LINE +
          "<p>Stage: Behavioral.</p>" +
          "<p>Open the Applications Board in Purrf to see it.</p>",
      },
    ],
  }),

  {
    key: "mentorship.mentor_admitted",
    name: "Mentor admitted",
    service: "mentorship",
    mode: "automatic",
    trigger:
      "When a mentor application is moved to Admitted — by staff, or by a screening rule that admits it outright",
    recipients: "The admitted mentor",
    unverified: {},
    variants: [
      {
        label: "A round is open",
        subject:
          "Welcome to Circle Cat Mentorship! Your application has been approved",
        body:
          "<p>Dear Taylor,</p>" +
          "<p>Thank you for applying to be a mentor at Circle Cat. We are thrilled to let you know that your application has been approved—welcome to the mentorship program!</p>" +
          "<p>There is just one final step before we can pair you with a mentee. Please log in to Purrf, go to your Personal Dashboard, and complete the mentorship registration form for Mentorship 2026 Fall. This form helps us understand your preferences and expertise so we can find the best possible match for you. Please note that we won't be able to match you without it.</p>" +
          "<p>Key Dates:</p>" +
          "<ul>" +
          "<li>Registration Deadline: October 12, 2026, at 11:59 PM (America/Los_Angeles)</li>" +
          "<li>Matching Results: Expected on October 20, 2026 (America/Los_Angeles)</li>" +
          "</ul>" +
          M_FOOTER,
      },
      {
        label: "No round open yet",
        subject:
          "Welcome to Circle Cat Mentorship! Your application has been approved",
        body:
          "<p>Dear Taylor,</p>" +
          "<p>Thank you for applying to be a mentor at Circle Cat. We are thrilled to let you know that your application has been approved—welcome to the mentorship program!</p>" +
          "<p>Registration for the upcoming round is not open just yet, but we will notify you as soon as it goes live. Once it opens, you'll need to complete a quick mentorship registration form on your Personal Dashboard. This will help us learn more about your topic preferences and ideal mentee match so we can pair you successfully.</p>" +
          "<p>We will be in touch soon with the next steps!</p>" +
          M_FOOTER,
      },
    ],
  },
  {
    key: "mentorship.matching_run_completed",
    name: "Matching run finished",
    service: "mentorship",
    mode: "automatic",
    trigger: "When a matching run finishes, or stops with an error",
    recipients: "The administrator who started the run",
    unverified: {},
    variants: [
      {
        label: "Finished",
        subject: "Mentorship matching has finished for Mentorship 2026 Fall",
        body:
          "<p>Hello,</p>" +
          "<p>The matching run you started for Mentorship 2026 Fall has finished.</p>" +
          "<p>It scored 42 mentees against 37 mentors and took 48 minutes.</p>" +
          "<p>Nothing has been published yet. No pairing exists until somebody reviews these results and applies them.</p>" +
          M_FOOTER,
      },
      {
        label: "Failed",
        subject: "Mentorship matching did not finish for Mentorship 2026 Fall",
        body:
          "<p>Hello,</p>" +
          "<p>The matching run you started for Mentorship 2026 Fall stopped before it produced results.</p>" +
          "<p><code>Scoring timed out after 3600 seconds</code></p>" +
          "<p>Nothing was changed. Starting a new run for this round is safe.</p>" +
          M_FOOTER,
      },
    ],
  },

  {
    key: "user.block_requested",
    name: "Block request waiting for decision",
    service: "users",
    mode: "automatic",
    trigger: "When someone raises a request to block a user",
    recipients: "The reviewer named on the request",
    unverified: {},
    variants: [
      {
        label: null,
        subject: "A block request is waiting for your decision",
        body:
          "<p>Alex Chen has asked you to decide whether Casey Morgan should be blocked from Purrf.</p>" +
          "<p>Reason given: Repeated no-shows at mentorship meetings</p>" +
          "<p>Open the Accounts page in Purrf to approve or reject the request.</p>" +
          M_FOOTER,
      },
    ],
  },
  {
    key: "user.block_request_reassigned",
    name: "Block request reassigned",
    service: "users",
    mode: "automatic",
    trigger: "When a pending block request is moved to a different reviewer",
    recipients: "The new reviewer and the previous reviewer",
    unverified: {},
    variants: [
      {
        label: null,
        subject: "A block request has been reassigned",
        body:
          "<p>The block request about Casey Morgan is now with Sam Patel.</p>" +
          "<p>If that is you, open the Accounts page in Purrf to decide it. If it is not, there is nothing left for you to do.</p>" +
          M_FOOTER,
      },
    ],
  },
  {
    key: "user.block_request_decided",
    name: "Block request decided",
    service: "users",
    mode: "automatic",
    trigger: "When the reviewer approves or rejects a block request",
    recipients: "Whoever raised the request",
    unverified: {},
    variants: [
      {
        label: "Approved",
        subject: "Your block request was approved",
        body:
          "<p>Sam Patel has approved the block request you raised about Casey Morgan.</p>" +
          "<p>Casey Morgan is now blocked from Purrf.</p>" +
          "<p>Note: Confirmed with the mentorship team.</p>" +
          M_FOOTER,
      },
      {
        label: "Rejected",
        subject: "Your block request was rejected",
        body:
          "<p>Sam Patel has rejected the block request you raised about Casey Morgan.</p>" +
          "<p>Casey Morgan has not been blocked.</p>" +
          M_FOOTER,
      },
    ],
  },
];

/** Not built yet. Shown so the list reads as something that will grow. */
export const PLANNED_TEMPLATES = [
  {
    key: "inbox.needs_reply_reminder.mentorship",
    name: "Inbox: new mail needs reply (reminder)",
    service: "mentorship",
    mode: "automatic",
    planned: true,
    trigger:
      "When mail in the Mentorship inbox has needed a reply for too long",
    recipients: "Holders of the Mentorship inbox permission",
    unverified: { recipients: true },
    variants: [],
  },
  {
    key: "inbox.needs_reply_reminder.recruiting",
    name: "Inbox: new mail needs reply (reminder)",
    service: "recruiting",
    mode: "automatic",
    planned: true,
    trigger:
      "When mail in the Recruiting inbox has needed a reply for too long",
    recipients: "Holders of the Recruiting inbox permission",
    unverified: { recipients: true },
    variants: [],
  },
];

export const TEMPLATES = [
  ...MANUAL_TEMPLATES,
  ...AUTOMATIC_TEMPLATES,
  ...PLANNED_TEMPLATES,
];
