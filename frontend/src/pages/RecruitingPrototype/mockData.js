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
    isViewed: false,
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
    isViewed: true,
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
    isViewed: true,
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
    isViewed: true,
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
    isViewed: true,
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

/** Returns the applications for a given job id, grouped by stage key. */
export function applicationsByStage(jobId) {
  const grouped = {};
  for (const app of APPLICATIONS) {
    if (app.jobId !== jobId) continue;
    (grouped[app.stage] ||= []).push(app);
  }
  return grouped;
}
