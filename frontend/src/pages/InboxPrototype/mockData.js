/**
 * Placeholder people, postings and mail for the inbox prototype.
 *
 * This bundle is published to a public URL, so every name and address here is
 * invented, and every address sits under a reserved example domain. The set is
 * chosen to cover each state an inbox row has to render — matched sender,
 * alternative-email match, unknown sender, auto-reply, bounce, archived,
 * assigned, awaiting reply and already replied — not to look like real mail.
 *
 * Times are wall-clock strings (`YYYY-MM-DDTHH:MM`) so they compare as strings
 * and render the same in every timezone.
 */

/** Every alias is a Gmail Send-As alias on one mailbox. */
export const ALIASES = {
  mentorship: "mentorship@circlecat.org",
  recruiting: "recruiting@circlecat.org",
  inquiries: "inquiries@circlecat.org",
};

/**
 * The three services sharing the one Inbox. `permission` is what lets a viewer
 * see and act on that service's threads; `badgeClass` gives each service its
 * own colour so mixed rows read at a glance.
 */
export const SERVICES = [
  {
    key: "mentorship",
    label: "Mentorship",
    alias: ALIASES.mentorship,
    permission: "mentorship.admin.write",
    badgeClass: "border-teal-200 bg-teal-50 text-teal-800",
  },
  {
    key: "recruiting",
    label: "Recruiting",
    alias: ALIASES.recruiting,
    permission: "recruiting.application.advance",
    badgeClass: "border-indigo-200 bg-indigo-50 text-indigo-800",
  },
  {
    key: "inquiries",
    label: "Inquiries",
    alias: ALIASES.inquiries,
    permission: "inquiries.manage",
    badgeClass: "border-stone-300 bg-stone-100 text-stone-700",
  },
];

/** The clock the prototype starts at; every local action ticks it forward. */
export const NOW = "2026-09-30T10:00";

/** Mentorship rounds, newest first. */
export const ROUNDS = ["Fall 2026", "Spring 2026", "Fall 2025", "Spring 2025"];
export const CURRENT_ROUND = "Fall 2026";

/**
 * Postings. EMPLOYMENT jobs are what Recruiting threads assign to; the two
 * ACTIVITY postings are the mentorship registrations, whose application
 * threads belong to the Mentorship service.
 */
export const JOBS = {
  backend: { title: "Backend Engineer", type: "EMPLOYMENT" },
  frontend: { title: "Frontend Engineer", type: "EMPLOYMENT" },
  designer: { title: "Product Designer", type: "EMPLOYMENT" },
  analyst: { title: "Data Analyst", type: "EMPLOYMENT" },
  mentee: { title: "Mentee 2026", type: "ACTIVITY" },
  mentor: { title: "Mentor 2026", type: "ACTIVITY" },
};

/**
 * Users the sender lookup can resolve to. A sender matches on the primary
 * email or on any alternative email.
 */
export const USERS = [
  {
    userId: 1234,
    name: "Wang Xiao",
    primaryEmail: "wang.xiao@example.com",
    alternativeEmails: ["xiaowang.dev@example.net"],
    rounds: ["Spring 2026", "Fall 2026"],
    applications: [
      { id: 36, job: "mentee", status: "Accepted", submitted: "2026-02-10" },
    ],
  },
  {
    userId: 1301,
    name: "Chen Meiling",
    primaryEmail: "meiling.chen@example.com",
    alternativeEmails: ["mchen.personal@example.org"],
    rounds: ["Fall 2025"],
    applications: [],
  },
  {
    userId: 1402,
    name: "Arjun Mehta",
    primaryEmail: "arjun.mehta@example.com",
    alternativeEmails: [],
    rounds: [],
    applications: [
      { id: 52, job: "frontend", status: "Rejected", submitted: "2026-04-02" },
      {
        id: 88,
        job: "backend",
        status: "In progress",
        submitted: "2026-08-19",
      },
    ],
  },
  {
    userId: 1418,
    name: "Sofia Ramirez",
    primaryEmail: "sofia.ramirez@example.com",
    alternativeEmails: ["sofia.r.work@example.net"],
    rounds: [],
    applications: [
      { id: 31, job: "analyst", status: "Rejected", submitted: "2026-01-14" },
      { id: 57, job: "analyst", status: "Rejected", submitted: "2026-06-03" },
    ],
  },
  {
    userId: 1520,
    name: "Liam Novak",
    primaryEmail: "liam.novak@example.com",
    alternativeEmails: [],
    rounds: ["Spring 2025", "Fall 2026"],
    applications: [],
  },
  {
    userId: 1555,
    name: "Priya Nair",
    primaryEmail: "priya.nair@example.com",
    alternativeEmails: [],
    rounds: ["Fall 2025", "Spring 2026", "Fall 2026"],
    applications: [
      { id: 72, job: "mentor", status: "Accepted", submitted: "2026-07-28" },
    ],
  },
  {
    userId: 1603,
    name: "Tomas Silva",
    primaryEmail: "tomas.silva@example.com",
    alternativeEmails: [],
    rounds: [],
    applications: [
      {
        id: 95,
        job: "frontend",
        status: "In progress",
        submitted: "2026-09-01",
      },
    ],
  },
  {
    userId: 1610,
    name: "Hana Kobayashi",
    primaryEmail: "hana.kobayashi@example.com",
    alternativeEmails: ["hana.k@example.org"],
    rounds: [],
    applications: [
      { id: 104, job: "backend", status: "Submitted", submitted: "2026-09-12" },
    ],
  },
  {
    userId: 1702,
    name: "Daniel Okafor",
    primaryEmail: "daniel.okafor@example.com",
    alternativeEmails: [],
    rounds: [],
    applications: [
      { id: 41, job: "mentee", status: "In progress", submitted: "2026-08-30" },
    ],
  },
  {
    userId: 1715,
    name: "Elena Petrova",
    primaryEmail: "elena.petrova@example.com",
    alternativeEmails: [],
    rounds: ["Fall 2026"],
    applications: [],
  },
  {
    userId: 1720,
    name: "Marcus Lee",
    primaryEmail: "marcus.lee@example.com",
    alternativeEmails: [],
    rounds: [],
    applications: [
      {
        id: 110,
        job: "analyst",
        status: "In progress",
        submitted: "2026-09-05",
      },
    ],
  },
  {
    userId: 1788,
    name: "Yuna Park",
    primaryEmail: "yuna.park@example.com",
    alternativeEmails: [],
    rounds: [],
    applications: [],
  },
];

const M = ALIASES.mentorship;
const R = ALIASES.recruiting;
const Q = ALIASES.inquiries;
const DAEMON = "mailer-daemon@googlemail.com";

const human = (id, direction, from, to, at, body, attachments = []) => ({
  id,
  direction,
  from,
  to,
  at,
  body,
  kind: "human",
  attachments,
});

const autoReply = (id, from, to, at, body) => ({
  id,
  direction: "in",
  from,
  to,
  at,
  body,
  kind: "auto_reply",
});

const bounce = (id, to, at, bouncedTo) => ({
  id,
  direction: "in",
  from: DAEMON,
  to,
  at,
  body: `Address not found. Your message wasn't delivered to ${bouncedTo} because the address couldn't be found, or is unable to receive mail.`,
  kind: "bounce",
  bouncedTo,
});

/**
 * `assignment` is `null` or `{userId, context}`, where `context` is
 * `{kind: "round", round}` or `{kind: "application", applicationId}`.
 * Inquiries threads are never assigned.
 *
 * `tracked` marks a thread that belongs to an application from the start
 * (it began with mail we sent about that application). Its service follows
 * the job type, so it can be neither reassigned nor moved.
 *
 * An inbound message may carry `attachments: [{name, size}]`.
 */
export const INITIAL_THREADS = [
  // Mentorship
  {
    id: "m1",
    service: "mentorship",
    subject: "Question about meeting cadence",
    archivedAt: null,
    assignment: null,
    messages: [
      human(
        "m1-1",
        "in",
        "wang.xiao@example.com",
        M,
        "2026-09-29T21:14",
        "Hi, my mentor and I can only meet every three weeks because of time zones. Is that acceptable for the Fall round, or do we need to meet every two weeks?",
      ),
    ],
  },
  {
    id: "m2",
    service: "mentorship",
    subject: "Can I still join the Fall round?",
    archivedAt: null,
    assignment: null,
    messages: [
      human(
        "m2-1",
        "in",
        "mchen.personal@example.org",
        M,
        "2026-09-29T16:40",
        "I missed the registration deadline by a few days. I took part last year and would love to join again as a mentee if there is still space.",
      ),
    ],
  },
  {
    id: "m3",
    service: "mentorship",
    subject: "Interested in becoming a mentor",
    archivedAt: null,
    assignment: null,
    messages: [
      human(
        "m3-1",
        "in",
        "jordan.blake@example.net",
        M,
        "2026-09-28T09:02",
        "A friend told me about your mentorship program. I have ten years in data engineering — how do I sign up as a mentor?",
      ),
    ],
  },
  {
    id: "m4",
    service: "mentorship",
    subject: "Requesting a different mentee",
    archivedAt: null,
    assignment: {
      userId: 1555,
      context: { kind: "round", round: "Fall 2026" },
    },
    messages: [
      human(
        "m4-1",
        "in",
        "priya.nair@example.com",
        M,
        "2026-09-22T11:20",
        "My mentee has not replied to three emails in two weeks. Is there anything you can do?",
      ),
      human(
        "m4-2",
        "out",
        M,
        "priya.nair@example.com",
        "2026-09-23T09:05",
        "Thanks for flagging this, Priya. We have reached out to your mentee and will get back to you by Friday.",
      ),
      human(
        "m4-3",
        "in",
        "priya.nair@example.com",
        M,
        "2026-09-29T18:30",
        "Still nothing on my side. Could I be matched with someone else for the rest of the round?",
      ),
    ],
  },
  {
    id: "m5",
    service: "mentorship",
    tracked: true,
    subject: "Your mentee application",
    archivedAt: null,
    assignment: {
      userId: 1702,
      context: { kind: "application", applicationId: 41 },
    },
    messages: [
      human(
        "m5-1",
        "out",
        R,
        "daniel.okafor@example.com",
        "2026-08-30T10:00",
        "We received your application for Mentee 2026. We will be in touch after the registration window closes.",
      ),
      human(
        "m5-2",
        "out",
        M,
        "daniel.okafor@example.com",
        "2026-09-20T14:12",
        "Your application has moved to the next step. Please complete the onboarding course before October 10.",
      ),
      human(
        "m5-3",
        "in",
        "daniel.okafor@example.com",
        M,
        "2026-09-29T08:47",
        "Thank you! The course link opens a blank page for me. Is there another way to access it?",
        [{ name: "blank-page.png", size: "412 KB" }],
      ),
    ],
  },
  {
    id: "m6",
    service: "mentorship",
    subject: "Midpoint check-in",
    archivedAt: null,
    assignment: {
      userId: 1715,
      context: { kind: "round", round: "Fall 2026" },
    },
    messages: [
      human(
        "m6-1",
        "in",
        "elena.petrova@example.com",
        M,
        "2026-09-24T13:00",
        "Could you remind me when the midpoint check-in form is due?",
      ),
      human(
        "m6-2",
        "out",
        M,
        "elena.petrova@example.com",
        "2026-09-25T09:30",
        "Hi Elena, the midpoint form is due October 15. You will get a reminder a week before.",
      ),
      autoReply(
        "m6-3",
        "elena.petrova@example.com",
        M,
        "2026-09-25T09:31",
        "I am out of the office until October 6 with limited access to email.",
      ),
    ],
  },
  {
    id: "m7",
    service: "mentorship",
    subject: "Fall 2026 pairing details",
    archivedAt: null,
    assignment: {
      userId: 1520,
      context: { kind: "round", round: "Fall 2026" },
    },
    messages: [
      human(
        "m7-1",
        "in",
        "liam.novak@example.com",
        M,
        "2026-09-18T19:22",
        "Please send pairing details to my old university address too, l.novak@alumni.example.edu — I check it more often.",
      ),
      human(
        "m7-2",
        "out",
        M,
        "l.novak@alumni.example.edu",
        "2026-09-19T10:04",
        "Hi Liam, here are your pairing details for Fall 2026.",
      ),
      bounce("m7-3", M, "2026-09-19T10:05", "l.novak@alumni.example.edu"),
    ],
  },
  {
    id: "m8",
    service: "mentorship",
    subject: "Partnership opportunity for your mentees",
    archivedAt: "2026-09-21T15:00",
    assignment: null,
    messages: [
      human(
        "m8-1",
        "in",
        "events@partnerco.example",
        M,
        "2026-09-20T07:45",
        "We run career fairs and would love to offer your mentees a discounted ticket.",
      ),
    ],
  },
  {
    id: "m9",
    service: "mentorship",
    subject: "Thank you for the workshop",
    archivedAt: null,
    assignment: null,
    messages: [
      human(
        "m9-1",
        "in",
        "yuna.park@example.com",
        M,
        "2026-09-26T20:10",
        "The career workshop last week was great. Will the slides be shared?",
      ),
      human(
        "m9-2",
        "out",
        M,
        "yuna.park@example.com",
        "2026-09-27T09:15",
        "Glad you enjoyed it! The slides are on the event page.",
      ),
    ],
  },

  // Recruiting
  {
    id: "r1",
    service: "recruiting",
    subject: "Follow-up on my interview",
    archivedAt: null,
    assignment: null,
    messages: [
      human(
        "r1-1",
        "in",
        "arjun.mehta@example.com",
        R,
        "2026-09-29T17:05",
        "I interviewed for the backend role last Tuesday. Is there any update on next steps?",
      ),
    ],
  },
  {
    id: "r2",
    service: "recruiting",
    subject: "Can I reapply?",
    archivedAt: null,
    assignment: null,
    messages: [
      human(
        "r2-1",
        "in",
        "sofia.r.work@example.net",
        R,
        "2026-09-29T12:18",
        "I was turned down for the analyst role in June. I have since finished a SQL certification — would it make sense to apply again?",
      ),
    ],
  },
  {
    id: "r3",
    service: "recruiting",
    subject: "Resume for any open role",
    archivedAt: null,
    assignment: null,
    messages: [
      human(
        "r3-1",
        "in",
        "kevin.zhou@example.net",
        R,
        "2026-09-28T22:40",
        "Please find my resume attached. I am open to any engineering role.",
        [
          { name: "Kevin_Zhou_Resume.pdf", size: "182 KB" },
          { name: "Portfolio_Links.docx", size: "24 KB" },
        ],
      ),
    ],
  },
  {
    id: "r4",
    service: "recruiting",
    subject: "Do you offer internships?",
    archivedAt: null,
    assignment: null,
    messages: [
      human(
        "r4-1",
        "in",
        "liam.novak@example.com",
        R,
        "2026-09-27T15:33",
        "I am a mentee this round. Are there internship openings I could apply for?",
      ),
    ],
  },
  {
    id: "r5",
    service: "recruiting",
    subject: "Take-home assignment question",
    archivedAt: null,
    assignment: {
      userId: 1603,
      context: { kind: "application", applicationId: 95 },
    },
    messages: [
      human(
        "r5-1",
        "in",
        "tomas.silva@example.com",
        R,
        "2026-09-24T10:11",
        "Should the take-home be written in TypeScript or is JavaScript fine?",
      ),
      human(
        "r5-2",
        "out",
        R,
        "tomas.silva@example.com",
        "2026-09-24T16:00",
        "Either is fine — use whichever you are most comfortable with.",
      ),
      human(
        "r5-3",
        "in",
        "tomas.silva@example.com",
        R,
        "2026-09-29T09:50",
        "Thanks. One more: can I have until Monday instead of Friday?",
      ),
    ],
  },
  {
    id: "r6",
    service: "recruiting",
    subject: "Scheduling your first interview",
    archivedAt: null,
    assignment: {
      userId: 1610,
      context: { kind: "application", applicationId: 104 },
    },
    messages: [
      human(
        "r6-1",
        "in",
        "hana.kobayashi@example.com",
        R,
        "2026-09-25T08:00",
        "I can do any afternoon next week for the first interview.",
      ),
      human(
        "r6-2",
        "out",
        R,
        "hana.kobayashi@example.com",
        "2026-09-26T11:00",
        "Great — does Wednesday at 3pm work?",
      ),
      autoReply(
        "r6-3",
        "hana.kobayashi@example.com",
        R,
        "2026-09-26T11:01",
        "Out of office: I am travelling and will reply after September 30.",
      ),
    ],
  },
  {
    id: "r7",
    service: "recruiting",
    subject: "Updated phone number",
    archivedAt: null,
    assignment: {
      userId: 1720,
      context: { kind: "application", applicationId: 110 },
    },
    messages: [
      human(
        "r7-1",
        "in",
        "marcus.lee@example.com",
        R,
        "2026-09-23T14:25",
        "My phone number changed. Also, please copy my assistant at assist@marcuslee.example on scheduling.",
      ),
      human(
        "r7-2",
        "out",
        R,
        "assist@marcuslee.example",
        "2026-09-24T09:40",
        "Hello, following up on Marcus's interview scheduling.",
      ),
      bounce("r7-3", R, "2026-09-24T09:41", "assist@marcuslee.example"),
    ],
  },
  {
    id: "r8",
    service: "recruiting",
    subject: "Demo: recruiting software for small teams",
    archivedAt: "2026-09-22T10:00",
    assignment: null,
    messages: [
      human(
        "r8-1",
        "in",
        "sales@hiretool.example",
        R,
        "2026-09-21T13:15",
        "Would you have 20 minutes for a demo of our applicant tracking system?",
      ),
    ],
  },
  {
    id: "r9",
    service: "recruiting",
    subject: "Where do I update my address?",
    archivedAt: null,
    assignment: null,
    messages: [
      human(
        "r9-1",
        "in",
        "yuna.park@example.com",
        R,
        "2026-09-25T18:02",
        "I moved recently. Where can I update my mailing address?",
      ),
      human(
        "r9-2",
        "out",
        R,
        "yuna.park@example.com",
        "2026-09-26T10:30",
        "You can update it on your profile page under Contact.",
      ),
    ],
  },

  // Inquiries
  {
    id: "q1",
    service: "inquiries",
    subject: "Donation receipt request",
    archivedAt: null,
    assignment: null,
    messages: [
      human(
        "q1-1",
        "in",
        "a.donor@example.org",
        Q,
        "2026-09-29T11:00",
        "Could you send me a receipt for my donation in August for tax purposes?",
      ),
    ],
  },
  {
    id: "q2",
    service: "inquiries",
    subject: "Volunteer opportunities",
    archivedAt: null,
    assignment: null,
    messages: [
      human(
        "q2-1",
        "in",
        "elena.petrova@example.com",
        Q,
        "2026-09-28T19:45",
        "Besides mentoring, are there other ways I can volunteer with CircleCat?",
      ),
    ],
  },
  {
    id: "q3",
    service: "inquiries",
    subject: "Speaking at your community event",
    archivedAt: null,
    assignment: null,
    messages: [
      human(
        "q3-1",
        "in",
        "mchen.personal@example.org",
        Q,
        "2026-09-27T10:20",
        "I would be happy to give a talk on career transitions at a future community event.",
      ),
    ],
  },
  {
    id: "q4",
    service: "inquiries",
    subject: "Press inquiry",
    archivedAt: null,
    assignment: null,
    messages: [
      human(
        "q4-1",
        "in",
        "press@newsdaily.example",
        Q,
        "2026-09-24T09:00",
        "We are writing a piece on nonprofit tech mentorship. Could someone speak with us?",
      ),
      human(
        "q4-2",
        "out",
        Q,
        "press@newsdaily.example",
        "2026-09-25T10:15",
        "Thanks for reaching out. Could you share your deadline and questions?",
      ),
      autoReply(
        "q4-3",
        "press@newsdaily.example",
        Q,
        "2026-09-25T10:16",
        "Automatic reply: I am on leave until October 2.",
      ),
    ],
  },
  {
    id: "q5",
    service: "inquiries",
    subject: "Sponsorship follow-up",
    archivedAt: null,
    assignment: null,
    messages: [
      human(
        "q5-1",
        "in",
        "info@oldcompany.example",
        Q,
        "2026-09-20T16:00",
        "We sponsored your event last year and would like to discuss this year.",
      ),
      human(
        "q5-2",
        "out",
        Q,
        "info@oldcompany.example",
        "2026-09-22T09:00",
        "Thank you — we would love to talk. Are you free next week?",
      ),
      bounce("q5-3", Q, "2026-09-22T09:01", "info@oldcompany.example"),
    ],
  },
  {
    id: "q6",
    service: "inquiries",
    subject: "Boost your website traffic",
    archivedAt: "2026-09-19T08:00",
    assignment: null,
    messages: [
      human(
        "q6-1",
        "in",
        "growth@seo-agency.example",
        Q,
        "2026-09-18T23:10",
        "We can get your site to the first page of search results in 30 days.",
      ),
    ],
  },
  {
    id: "q7",
    service: "inquiries",
    subject: "Reference letter request",
    archivedAt: null,
    assignment: null,
    messages: [
      human(
        "q7-1",
        "in",
        "priya.nair@example.com",
        Q,
        "2026-09-21T12:00",
        "Could CircleCat provide a letter confirming my volunteer hours?",
      ),
      human(
        "q7-2",
        "out",
        Q,
        "priya.nair@example.com",
        "2026-09-22T10:00",
        "Of course. How many hours should we confirm, and for which period?",
      ),
      human(
        "q7-3",
        "in",
        "priya.nair@example.com",
        Q,
        "2026-09-29T20:05",
        "About 40 hours between September 2025 and June 2026. Thank you!",
      ),
    ],
  },
  {
    id: "q8",
    service: "inquiries",
    subject: "Is there a mentorship program for engineers?",
    archivedAt: null,
    assignment: null,
    messages: [
      human(
        "q8-1",
        "in",
        "hana.k@example.org",
        Q,
        "2026-09-29T07:30",
        "I am applying for your backend role and also want to find a mentor. Is there a program I can join?",
      ),
    ],
  },
];
