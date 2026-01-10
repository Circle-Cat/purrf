import MentorshipInfoBanner from "@/pages/PersonalDashboard/components/MentorshipInfoBanner";
import { useMentorshipData } from "@/pages/PersonalDashboard/hooks/useMentorshipData";

/**
 * PersonalDashboard
 *
 * Main dashboard page for the current user.
 *
 * Responsibilities:
 * - Display a welcome header.
 * - Load mentorship-related data via `useMentorshipData`.
 * - Pass mentorship state and actions down to `MentorshipInfoBanner`.
 *
 * This component itself contains no business logic;
 * all data fetching and state management are delegated to hooks.
 *
 * @returns {JSX.Element}
 */
const PersonalDashboard = () => {
  const {
    registration, // Registration data for the current or most recent round
    isRegistrationOpen, // Whether the registration period is currently open
    isFeedbackEnabled, // Whether the feedback phase is currently active
    saveRegistration, // Function to submit or update registration data
    pastPartners, // List of past mentorship partners
    isPartnersLoading, // Whether partner data is currently loading
    loadPastPartners, // Function to trigger loading of past partners
    refreshRegistration, // Function to refresh registration data
  } = useMentorshipData();

  return (
    <div className="personal-dashboard">
      {/* Welcome header */}
      <div className="flex items-start justify-between mb-5 shrink-0">
        <div className="flex items-center gap-2">
          <span role="img" aria-label="clapping hands" className="text-xl">
            &#x1F44F;
          </span>
          <h2 className="m-0 text-lg font-medium">Welcome</h2>
        </div>
      </div>

      {/* Mentorship information banner */}
      <MentorshipInfoBanner
        registration={registration}
        isRegistrationOpen={isRegistrationOpen}
        isFeedbackEnabled={isFeedbackEnabled}
        onSaveRegistration={saveRegistration}
        pastPartners={pastPartners}
        isPartnersLoading={isPartnersLoading}
        onLoadPastPartners={loadPastPartners}
        refreshRegistration={refreshRegistration}
      />
    </div>
  );
};

export default PersonalDashboard;
