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

  return {
    globalPreferences: {
      ...currentRegistration?.globalPreferences,
      specificIndustry: industryObj,
      skillsets: skillsetObj,
    },
    roundPreferences: {
      ...currentRegistration?.roundPreferences,
      maxPartners: formData.partnerCapacity,
      goal: formData.goal,
      expectedPartnerIds: formData.selectedPartners.map((p) => p.id),
      unexpectedPartnerIds: formData.excludedPartners.map((p) => p.id),
    },
  };
};
