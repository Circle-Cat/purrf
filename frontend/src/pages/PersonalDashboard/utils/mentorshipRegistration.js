export const CAREER_TRANSITION_OPTIONS = [
  {
    id: "none",
    label: "No. My undergraduate background was already in the CS field.",
  },
  {
    id: "path_a",
    label:
      "Yes, Path A: Non-CS undergraduate background → CS master's degree → technical role.",
  },
  {
    id: "path_b",
    label:
      "Yes, Path B: Non-CS undergraduate background → transitioned into a technical role after several years of work experience.",
  },
  { id: "other", label: "Other: Please briefly describe." },
];

export const REGION_OPTIONS = [
  { id: "us", label: "United States" },
  { id: "canada", label: "Canada" },
  { id: "china", label: "China" },
  { id: "other", label: "Other region: Please specify." },
];

export const EXTERNAL_MENTORING_OPTIONS = [
  { id: "none", label: "No" },
  { id: "1_to_3", label: "1-3 mentoring experiences" },
  { id: "3_plus", label: "More than 3 mentoring experiences" },
];

export const CURRENT_BACKGROUND_OPTIONS = [
  {
    id: "cs_grad",
    label:
      "All degrees within the CS field, currently following a technical job-search path.",
  },
  {
    id: "non_cs_cs_master",
    label:
      "Non-CS undergraduate background, currently pursuing or recently completed a CS master's degree, looking for a first technical role.",
  },
  {
    id: "non_tech_to_tech",
    label:
      "Have previous non-technical work experience and aiming to transition into a technical role.",
  },
  {
    id: "non_cs_starting",
    label:
      "Non-CS undergraduate background, have not started transitioning into CS yet, but are considering getting started.",
  },
  { id: "other", label: "Other: Please specify." },
];

export const CURRENT_STAGE_OPTIONS = [
  {
    id: "job_searching",
    label: "Currently job searching / preparing for job applications.",
  },
  {
    id: "employed_growing",
    label: "Currently employed, hoping to grow / advance in my career.",
  },
  {
    id: "changing_direction",
    label: "Hoping to switch tracks / transition into a different field.",
  },
  {
    id: "grad_school",
    label: "Planning for graduate school / applications.",
  },
];

export const TIME_URGENCY_OPTIONS = [
  { id: "within_3_months", label: "Need support within 3 months." },
  { id: "within_6_months", label: "Within 6 months." },
  { id: "1_year_plus", label: "More than 1 year; long-term planning." },
  { id: "no_timeline", label: "No clear timeline yet." },
];

export const TARGET_REGION_OPTIONS = [
  { id: "china", label: "China" },
  { id: "us", label: "United States" },
  { id: "canada", label: "Canada" },
  { id: "other", label: "Other region: Please specify." },
];

/**
 * Industry options used in the mentorship registration form.
 * Each option represents a selectable industry preference.
 */
export const INDUSTRY_CONFIG = [
  { id: "swe", name: "Software Engineering" },
  { id: "uiux", name: "UI / UX" },
  { id: "ds", name: "Data Science" },
  { id: "pm", name: "Product Management" },
];

/**
 * Skillset options used in the mentorship registration form.
 * Users can select multiple skillsets depending on their role.
 */
export const SKILLSET_CONFIG = [
  { id: "resumeGuidance", name: "Resume/LinkedIn Profile" },
  { id: "careerPathGuidance", name: "Career Path Guidance" },
  { id: "experienceSharing", name: "Experience Sharing" },
  { id: "industryTrends", name: "Industry Trends" },
  { id: "technicalSkills", name: "Technical Skills Development" },
  { id: "softSkills", name: "Soft Skills Enhancement" },
  { id: "networking", name: "Networking" },
  { id: "projectManagement", name: "Project Management" },
  { id: "leadership", name: "Leadership" },
  { id: "communicationSkills", name: "Communication Skills" },
];

/**
 * Map backend registration data into frontend form state.
 *
 * This function converts API response data into a structure
 * that can be directly consumed by the registration form UI.
 *
 * @param {Object} registration - Current user's registration data from backend
 * @param {Array<Object>} allPastPartners - List of all past partners
 * @returns {Object} Form-compatible state object
 */
export const mapRegistrationToForm = (registration, allPastPartners) => {
  const globalPref = registration?.globalPreferences || {};
  const roundPref = registration?.roundPreferences || {};
  const survey = globalPref.profileSurvey || {};

  return {
    industries: INDUSTRY_CONFIG.filter(
      (c) => globalPref.specificIndustry?.[c.id] === true,
    ),
    skillsets: SKILLSET_CONFIG.filter(
      (c) => globalPref.skillsets?.[c.id] === true,
    ),
    partnerCapacity: roundPref.maxPartners || 1,
    goal: roundPref.goal || "",
    selectedPartners: allPastPartners
      .filter((p) => roundPref.expectedPartnerIds?.includes(p.id))
      .map((p) => ({
        id: p.id,
        name: p.preferredName || `${p.firstName} ${p.lastName}`,
      })),
    excludedPartners: allPastPartners
      .filter((p) => roundPref.unexpectedPartnerIds?.includes(p.id))
      .map((p) => ({
        id: p.id,
        name: p.preferredName || `${p.firstName} ${p.lastName}`,
      })),
    // Mentor survey fields
    careerTransition: survey.careerTransition || "",
    careerTransitionOther: survey.careerTransitionOther || "",
    region: survey.region || "",
    regionOther: survey.regionOther || "",
    externalMentoringExp: survey.externalMentoringExp || "",
    // Mentee survey fields
    currentBackground: survey.currentBackground || "",
    currentBackgroundOther: survey.currentBackgroundOther || "",
    targetRegion: survey.targetRegion || "",
    targetRegionOther: survey.targetRegionOther || "",
    // Mentee round fields
    currentStage: roundPref.currentStage || "",
    timeUrgency: roundPref.timeUrgency || "",
  };
};

/**
 * Map frontend form state back into backend API format.
 *
 * This function transforms selected industries, skillsets,
 * and partner preferences into the structure expected by the API.
 *
 * @param {Object} formData - Current form state
 * @param {Object} currentRegistration - Existing registration data
 * @returns {Object} API-ready registration payload
 */
export const mapFormToApi = (formData, currentRegistration) => {
  const industryObj = INDUSTRY_CONFIG.reduce(
    (acc, c) => ({
      ...acc,
      [c.id]: formData.industries.some((s) => s.id === c.id),
    }),
    {},
  );

  const skillsetObj = SKILLSET_CONFIG.reduce(
    (acc, c) => ({
      ...acc,
      [c.id]: formData.skillsets.some((s) => s.id === c.id),
    }),
    {},
  );

  const surveyEntries = {
    careerTransition: formData.careerTransition || undefined,
    careerTransitionOther:
      formData.careerTransition === "other"
        ? formData.careerTransitionOther
        : undefined,
    region: formData.region || undefined,
    regionOther: formData.region === "other" ? formData.regionOther : undefined,
    externalMentoringExp: formData.externalMentoringExp || undefined,
    currentBackground: formData.currentBackground || undefined,
    currentBackgroundOther:
      formData.currentBackground === "other"
        ? formData.currentBackgroundOther
        : undefined,
    targetRegion: formData.targetRegion || undefined,
    targetRegionOther:
      formData.targetRegion === "other"
        ? formData.targetRegionOther
        : undefined,
  };

  return {
    globalPreferences: {
      ...currentRegistration?.globalPreferences,
      specificIndustry: industryObj,
      skillsets: skillsetObj,
      profileSurvey: surveyEntries,
    },
    roundPreferences: {
      ...currentRegistration?.roundPreferences,
      maxPartners: formData.partnerCapacity,
      goal: formData.goal,
      expectedPartnerIds: formData.selectedPartners.map((p) => p.id),
      unexpectedPartnerIds: formData.excludedPartners.map((p) => p.id),
      currentStage: formData.currentStage || undefined,
      timeUrgency: formData.timeUrgency || undefined,
    },
  };
};
