/**
 * Short English labels for the registration survey's codes as the matching
 * results carry them. A code missing here is shown as is.
 */
const TRANSITION = {
  none_cs_background: "No CS background",
  via_cs_masters: "Via a CS master's",
  via_work_experience: "Via work experience",
  considering_transition: "Considering a transition",
};

const REGION = {
  us: "US",
  canada: "Canada",
  china: "China",
};

export const SURVEY_LABELS = Object.freeze({
  careerTransition: TRANSITION,
  transitionType: TRANSITION,
  developmentRegion: REGION,
  jobMarketRegion: REGION,
  externalMentoringExp: {
    none: "None",
    "1_to_3": "1–3",
    "3_plus": "3+",
  },
  urgency: {
    "3m": "Within 3 months",
    "6m": "Within 6 months",
    "1y_plus": "A year or more",
    no_timeline: "No timeline",
  },
  menteeStage: {
    job_searching: "Job searching",
    employed_growth: "Growing in their job",
    career_switch: "Switching careers",
    grad_planning: "Planning after graduation",
  },
  specificIndustry: {
    swe: "Software engineering",
    ds: "Data science",
    pm: "Product management",
    uiux: "UI/UX",
  },
  skills: {
    career_path_guidance: "Career path guidance",
    experience_sharing: "Experience sharing",
    industry_trends: "Industry trends",
    networking: "Networking",
    project_management: "Project management",
    resume_guidance: "Resume guidance",
    soft_skills: "Soft skills",
    technical_skills: "Technical skills",
  },
});

/**
 * The label for one survey answer, with the person's own words after it when
 * they gave any.
 *
 * @param {string} field - The profile key, e.g. "urgency".
 * @param {string|null} code - The answer's code.
 * @param {string|null} [other] - The `*_other` free text.
 * @returns {string|null} null when there is no answer.
 */
export const surveyLabel = (field, code, other) => {
  if (!code) return other || null;
  const label = SURVEY_LABELS[field]?.[code] ?? code;
  return other ? `${label} (${other})` : label;
};

/**
 * The labels of the keys set to true in a multi-choice answer, in the
 * answer's own order.
 *
 * @param {string} field - The profile key, e.g. "skills".
 * @param {Record<string, boolean>|null} answer
 * @returns {string[]}
 */
export const checkedLabels = (field, answer) =>
  Object.entries(answer ?? {})
    .filter(([, on]) => on)
    .map(([key]) => SURVEY_LABELS[field]?.[key] ?? key);

/**
 * "Name (ID n)", or "ID n" when the name did not resolve.
 *
 * @param {{userId: number, name: string|null}} person
 * @returns {string}
 */
export const personWithId = ({ userId, name }) =>
  name ? `${name} (ID ${userId})` : `ID ${userId}`;

/**
 * A score to two decimal places at most; "—" when there is none.
 *
 * @param {number|null} score
 * @returns {string}
 */
export const scoreLabel = (score) =>
  score == null ? "—" : String(Math.round(score * 100) / 100);

/** Where a round's latest matching run stands, as the API says it. */
export const RUN_STATUS = Object.freeze({
  NEVER_RUN: "never_run",
  RUNNING: "running",
  FAILED: "failed",
  UNUSABLE: "unusable",
  SUCCEEDED: "succeeded",
});
