/**
 * Mock data for the Recruiting v2 prototype (meeting demo only — no backend).
 *
 * Shapes mirror the v2 design:
 * - A job carries an ordered `stages` pipeline (data-driven) and a
 *   `mentorshipRole` implied by its template (no role picker in the UI).
 * - An application carries the applicant's contact info at the top level
 *   (name/email/phone) plus form answers and a profile snapshot
 *   (experience/education/resume) shown in the detail drawer.
 */

/** Ordered stage definitions with display labels and accent colors. */
export const STAGES = {
  recruiter_screening: {
    key: "recruiter_screening",
    label: "Screening",
    color: "sky",
  },
  behavioral: { key: "behavioral", label: "Behavioral", color: "violet" },
  tech: { key: "tech", label: "Tech", color: "amber" },
  board_review: { key: "board_review", label: "Board Review", color: "rose" },
  offer: { key: "offer", label: "Offer", color: "emerald" },
};

/** The three demo postings. Mentor auto-approves (no board), so it is informational. */
export const JOBS = [
  {
    id: 1,
    title: "Software Engineer Intern",
    kind: "employment",
    template: "Intern",
    mentorshipRole: null,
    stages: [
      "recruiter_screening",
      "behavioral",
      "tech",
      "board_review",
      "offer",
    ],
    description:
      "Volunteer residency: build real non-profit projects mentored by industry engineers.",
  },
  {
    id: 2,
    title: "Mentorship Program — Mentee",
    kind: "activity",
    template: "Mentee",
    mentorshipRole: "mentee",
    stages: ["recruiter_screening"],
    description:
      "1:1 career mentorship with an experienced tech mentor over a 3-4 month round.",
  },
  {
    id: 3,
    title: "Mentorship Program — Mentor",
    kind: "activity",
    template: "Mentor",
    mentorshipRole: "mentor",
    stages: [],
    description:
      "Auto-approved when the applicant signs in with a google.com work email.",
  },
];

/**
 * Applications for the Intern posting (job 1), spread across its 5 stages so the
 * swimlane board looks alive. Each has top-level contact info + a profile snapshot.
 */
export const APPLICATIONS = [
  {
    id: 101,
    jobId: 1,
    stage: "recruiter_screening",
    status: "pending",
    freezeUntil: null,
    applicant: {
      firstName: "Ann",
      lastName: "Liu",
      email: "ann.liu@gmail.com",
      phone: "+1 (415) 555-0142",
    },
    appliedAt: "2026-06-18T09:00:00Z",
    resumeUrl: "https://drive.google.com/file/ann-resume",
    education: [
      {
        school: "UC Berkeley",
        degree: "B.S. Computer Science",
        years: "2022 – 2026",
      },
    ],
    experience: [
      {
        company: "Campus Robotics Lab",
        title: "Research Assistant",
        years: "2024 – 2025",
      },
    ],
    formAnswers: {
      "Major or field of study": "Computer Science",
      "Current status": "Full-time student",
      "Why do you want to join?":
        "I want to contribute to a mission-driven engineering team and grow through real project work and mentorship.",
      "Fluent in Mandarin?": "YES",
    },
  },
  {
    id: 102,
    jobId: 1,
    stage: "recruiter_screening",
    status: "in_progress",
    freezeUntil: null,
    applicant: {
      firstName: "Wei",
      lastName: "Zhang",
      email: "wei.zhang@outlook.com",
      phone: "+1 (206) 555-0199",
    },
    appliedAt: "2026-06-17T14:30:00Z",
    resumeUrl: "https://drive.google.com/file/wei-resume",
    education: [
      {
        school: "University of Washington",
        degree: "B.S. Data Science",
        years: "2021 – 2025",
      },
    ],
    experience: [
      { company: "Startup XYZ", title: "Data Analyst Intern", years: "2024" },
    ],
    formAnswers: {
      "Major or field of study": "Data Science",
      "Current status": "Recent graduate",
      "Why do you want to join?":
        "I'm passionate about applying data science to social-impact problems and want hands-on industry experience.",
      "Fluent in Mandarin?": "YES",
    },
  },
  {
    id: 103,
    jobId: 1,
    stage: "behavioral",
    status: "in_progress",
    freezeUntil: null,
    applicant: {
      firstName: "Bob",
      lastName: "Chen",
      email: "bob.chen@gmail.com",
      phone: "+1 (650) 555-0177",
    },
    appliedAt: "2026-06-15T11:00:00Z",
    resumeUrl: "https://drive.google.com/file/bob-resume",
    education: [
      {
        school: "Stanford",
        degree: "M.S. Computer Science",
        years: "2023 – 2025",
      },
    ],
    experience: [{ company: "BigTech", title: "SWE Intern", years: "2024" }],
    formAnswers: {
      "Major or field of study": "Machine Learning",
      "Current status": "Recent graduate",
      "Why do you want to join?":
        "I admire CircleCat's Women-in-Tech mission and want to mentor and build alongside the team.",
      "Fluent in Mandarin?": "YES",
    },
  },
  {
    id: 104,
    jobId: 1,
    stage: "tech",
    status: "evaluated",
    freezeUntil: null,
    applicant: {
      firstName: "Cara",
      lastName: "Singh",
      email: "cara.singh@gmail.com",
      phone: "+1 (312) 555-0123",
    },
    appliedAt: "2026-06-12T16:45:00Z",
    resumeUrl: "https://drive.google.com/file/cara-resume",
    education: [
      {
        school: "UIUC",
        degree: "B.S. Computer Engineering",
        years: "2020 – 2024",
      },
    ],
    experience: [
      { company: "Cloud Co", title: "Backend Engineer", years: "2024 – 2025" },
      { company: "Dev Bootcamp", title: "TA", years: "2023" },
    ],
    formAnswers: {
      "Major or field of study": "Computer Science",
      "Current status": "Early-career professional",
      "Why do you want to join?":
        "I want to give back by building infrastructure for a non-profit while sharpening my system-design skills.",
      "Fluent in Mandarin?": "YES",
    },
  },
  {
    id: 105,
    jobId: 1,
    stage: "board_review",
    status: "pending",
    freezeUntil: null,
    applicant: {
      firstName: "Dana",
      lastName: "Park",
      email: "dana.park@gmail.com",
      phone: "+1 (917) 555-0188",
    },
    appliedAt: "2026-06-08T10:15:00Z",
    resumeUrl: "https://drive.google.com/file/dana-resume",
    education: [
      { school: "NYU", degree: "B.A. Cognitive Science", years: "2019 – 2023" },
    ],
    experience: [
      {
        company: "Fintech Inc",
        title: "Software Engineer",
        years: "2023 – 2025",
      },
    ],
    formAnswers: {
      "Major or field of study": "Information Systems",
      "Current status": "Early-career professional",
      "Why do you want to join?":
        "I've supported Women in Tech through organizing CS workshops and want to deepen that impact here.",
      "Fluent in Mandarin?": "YES",
    },
  },
];

/** Example JSON-Schema form for the Apply prototype (job-specific Details section). */
export const SAMPLE_FORM_SCHEMA = {
  type: "object",
  required: ["major", "why"],
  properties: {
    major: {
      type: "string",
      title: "What is (or was) your major or field of study?",
      enum: [
        "Computer Science",
        "Data Science",
        "Cybersecurity",
        "Machine Learning",
        "Others",
      ],
    },
    status: {
      type: "string",
      title: "What is your current academic or professional status?",
      description: "Pick the option that best describes you today.",
      enum: [
        "Full-time student",
        "Recent graduate",
        "Early-career professional",
        "Others",
      ],
    },
    why: {
      type: "string",
      title:
        "In ≤300 words, why do you want to join and how will you participate?",
      description:
        "Be specific about how you'll arrange meetings and follow through on goals.",
      "x-widget": "textarea",
    },
    focus: {
      type: "array",
      title: "Which areas would you like to focus on? (choose up to 3)",
      items: {
        enum: [
          "Software Engineering",
          "Data Science",
          "Machine Learning",
          "Networking",
          "Soft Skills",
        ],
      },
    },
  },
};

/** Profile sections that a posting can require, in display order. */
export const PROFILE_FIELDS = [
  { key: "education", label: "Education" },
  { key: "experience", label: "Experience" },
  { key: "summary", label: "Summary" },
  { key: "resume", label: "Resume" },
];

/** The three requirement levels a profile section can take. */
export const REQ_LEVELS = ["off", "optional", "required"];

/**
 * Per-application activity trail (evaluations, comments, emails, stage changes),
 * newest first. Keyed by application id; apps without an entry start empty.
 */
export const ACTIVITY = {
  104: [
    {
      id: "a1",
      type: "evaluation",
      author: "Alice Chen",
      at: "2d ago",
      stage: "tech",
      overall: 3.7,
      criteria: [
        { label: "Coding", score: 4, note: "Clean, idiomatic solutions." },
        {
          label: "System design",
          score: 3,
          note: "Shaky on scaling, but coachable.",
        },
        { label: "Problem solving", score: 4, note: "Methodical approach." },
      ],
    },
    {
      id: "a2",
      type: "comment",
      author: "Bob Lin",
      at: "2d ago",
      text: "@Alice agreed — let's advance her to board review.",
    },
    {
      id: "a3",
      type: "email",
      direction: "in",
      at: "3d ago",
      subject: "Re: Tech interview",
      snippet: "Thursday 2pm works, thank you!",
    },
    {
      id: "a4",
      type: "email",
      direction: "out",
      at: "4d ago",
      subject: "Tech interview invite",
      snippet: "Proposing Thu/Fri this week.",
    },
    {
      id: "a5",
      type: "stage",
      author: "Alice Chen",
      at: "4d ago",
      from: "Behavioral",
      to: "Tech",
    },
    {
      id: "a6",
      type: "evaluation",
      author: "Carol Ng",
      at: "5d ago",
      stage: "behavioral",
      overall: 5,
      criteria: [
        {
          label: "Motivation & alignment",
          score: 5,
          note: "Deeply aligned with the mission.",
        },
        { label: "Teamwork", score: 5, note: "Collaborative, generous." },
        {
          label: "Ownership",
          score: 5,
          note: "Drove past projects end-to-end.",
        },
      ],
    },
  ],
  103: [
    {
      id: "b1",
      type: "comment",
      author: "Alice Chen",
      at: "1d ago",
      text: "Behavioral scheduled for tomorrow — @Carol can you take it?",
    },
    {
      id: "b2",
      type: "email",
      direction: "out",
      at: "2d ago",
      subject: "Behavioral interview invite",
      snippet: "A few slots this week.",
    },
    {
      id: "b3",
      type: "stage",
      author: "Alice Chen",
      at: "3d ago",
      from: "Screening",
      to: "Behavioral",
    },
  ],
  105: [
    {
      id: "d1",
      type: "evaluation",
      author: "Bob Lin",
      at: "6d ago",
      stage: "tech",
      overall: 4,
      criteria: [
        { label: "Coding", score: 4, note: "Solid fundamentals." },
        { label: "System design", score: 4, note: "Pragmatic trade-offs." },
        { label: "Problem solving", score: 4, note: "Good fit overall." },
      ],
    },
    {
      id: "d2",
      type: "stage",
      author: "Bob Lin",
      at: "6d ago",
      from: "Tech",
      to: "Board Review",
    },
  ],
};

/**
 * A candidate's other applications across postings, keyed by email (the stable
 * person identity). Each entry rolls up attempts to one posting, with a
 * per-attempt history for the drill-in detail.
 */
export const APPLICATION_HISTORY = {
  "cara.singh@gmail.com": [
    {
      id: "h-cara-mentee",
      jobTitle: "Mentorship Program — Mentee",
      attempts: 2,
      status: "rejected",
      lastAt: "2026-03-10",
      attemptsDetail: [
        {
          attempt: 1,
          outcome: "Rejected",
          at: "2025-11-02",
          note: "Strong profile but limited slots; encouraged to reapply.",
        },
        {
          attempt: 2,
          outcome: "Rejected",
          at: "2026-03-10",
          note: "Reapplied after the cooldown; narrowly missed the cohort.",
        },
      ],
    },
  ],
  "dana.park@gmail.com": [
    {
      id: "h-dana-mentee",
      jobTitle: "Mentorship Program — Mentee",
      attempts: 1,
      status: "hired",
      lastAt: "2025-08-20",
      attemptsDetail: [
        {
          attempt: 1,
          outcome: "Hired",
          at: "2025-08-20",
          note: "Completed the Summer 2025 mentee round.",
        },
      ],
    },
  ],
};

/** Returns the applications for a given job id, grouped by stage key. */
export function applicationsByStage(jobId) {
  const grouped = {};
  for (const app of APPLICATIONS) {
    if (app.jobId !== jobId) continue;
    (grouped[app.stage] ||= []).push({
      ...app,
      activity: ACTIVITY[app.id] ?? [],
    });
  }
  return grouped;
}

// ---------------------------------------------------------------------------
// Job review gate (the posting-lifecycle / approval flow)
// ---------------------------------------------------------------------------

/**
 * Current signed-in admin (the submitter). Deliberately NOT in REVIEWERS so the
 * "no self-review" rule is demonstrable.
 */
export const CURRENT_USER_ID = 100;

/** Holders of recruiting.job.approve — the approver pool (≥2 so submit is allowed). */
export const REVIEWERS = [
  { id: 1, name: "Alice Kim", email: "alice@circlecat.org" },
  { id: 2, name: "Bob Lee", email: "bob@circlecat.org" },
  { id: 3, name: "Chen Hua", email: "chen@circlecat.org" },
];

/** Posting status → badge label + Tailwind classes. */
export const POSTING_STATUS = {
  draft: {
    label: "草稿",
    badge: "bg-slate-100 text-slate-600 border-slate-200",
  },
  pending_review: {
    label: "待审核",
    badge: "bg-amber-100 text-amber-700 border-amber-200",
  },
  published: {
    label: "已发布",
    badge: "bg-emerald-100 text-emerald-700 border-emerald-200",
  },
  closed: {
    label: "已关闭",
    badge: "bg-slate-100 text-slate-400 border-slate-200",
  },
  published_pending_revision: {
    label: "已发布 · 改动待重审",
    badge: "bg-orange-100 text-orange-700 border-orange-200",
  },
};

/**
 * Seed postings covering every status for the review-gate demo. Shapes mirror a
 * JOBS row plus the review-gate fields (status / reviewerId / submitMessage /
 * rejectComment / rejectedBy / pendingRevision).
 */
export const INITIAL_POSTINGS = [
  {
    id: 201,
    title: "Mentorship Program — Mentee",
    kind: "activity",
    template: "Mentee",
    stages: ["recruiter_screening"],
    description:
      "1:1 career mentorship with an experienced tech mentor over a 3-4 month round.",
    status: "draft",
    reviewerId: null,
    submitMessage: "",
    rejectComment: "",
    rejectedBy: null,
    pendingRevision: null,
  },
  {
    id: 202,
    title: "Software Engineer Intern",
    kind: "employment",
    template: "Intern",
    stages: [
      "recruiter_screening",
      "behavioral",
      "tech",
      "board_review",
      "offer",
    ],
    description:
      "Volunteer residency: build real non-profit projects mentored by industry engineers.",
    status: "pending_review",
    reviewerId: 1,
    submitMessage: "按春招流程配的,麻烦看下 Tech 轮表单。",
    rejectComment: "",
    rejectedBy: null,
    pendingRevision: null,
  },
  {
    id: 203,
    title: "Mentorship Program — Mentor",
    kind: "activity",
    template: "Mentor",
    stages: [],
    description: "Guide a mentee 1:1 over a 3-4 month round.",
    status: "published",
    reviewerId: 2,
    submitMessage: "",
    rejectComment: "",
    rejectedBy: null,
    pendingRevision: null,
  },
  {
    id: 204,
    title: "2025 Spring Camp",
    kind: "activity",
    template: "Custom",
    stages: ["recruiter_screening", "board_review"],
    description: "Seasonal camp cohort (archived).",
    status: "closed",
    reviewerId: 3,
    submitMessage: "",
    rejectComment: "",
    rejectedBy: null,
    pendingRevision: null,
  },
  {
    id: 205,
    title: "Frontend Engineer Intern",
    kind: "employment",
    template: "Intern",
    stages: [
      "recruiter_screening",
      "behavioral",
      "tech",
      "board_review",
      "offer",
    ],
    description: "Frontend-focused residency.",
    status: "published_pending_revision",
    reviewerId: 1,
    submitMessage: "改了 2 个字段,请重审。",
    rejectComment: "",
    rejectedBy: null,
    pendingRevision: {
      changedFields: ["Tech 轮:字数上限题", "反 AI 声明题"],
      note: "新增字数上限 + 逐字校验。",
    },
  },
];

/** Postings awaiting review by the given reviewer id (initial + revision reviews). */
export function reviewsForUser(postings, userId) {
  return postings.filter(
    (p) =>
      (p.status === "pending_review" ||
        p.status === "published_pending_revision") &&
      p.reviewerId === userId,
  );
}

/** Reviewer display name by id, or "—" if unknown. */
export function reviewerName(id) {
  return REVIEWERS.find((r) => r.id === id)?.name ?? "—";
}
