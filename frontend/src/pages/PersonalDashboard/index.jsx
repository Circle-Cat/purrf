import MentorshipInfoBanner from "@/pages/PersonalDashboard/components/MentorshipInfoBanner";
import { WorkActivityDataCard } from "@/pages/PersonalDashboard/components/WorkActivityDataCard";
import MentorshipParticipantsCard from "@/pages/PersonalDashboard/components/MentorshipParticipantsCard";
import { useMentorshipData } from "@/pages/PersonalDashboard/hooks/useMentorshipData";
import { useWorkActivityData } from "@/pages/PersonalDashboard/hooks/useWorkActivityData";
import { useAuth } from "@/context/auth";
import { USER_ROLES } from "@/constants/UserRoles";

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
    canViewMatch, // Whether the matching result is visible to the user (e.g. during the announcement period)
    matchResult, // The Matching result data
    matchResultRoundName, // Display name of the matching result round
    roundSelectionData, // Sorted list of all rounds and the active round ID for the round selector
    selectedRoundId, // Currently selected round ID for the participant card
    handleRoundChange, // Callback to update the selected round
    participantDetails, // Round info, per-partner meeting overview, and user role
    refreshMeetings, // Trigger a refresh of meeting log data for the selected round
    isParticipantCardLoading, // Whether the participant card data is currently loading
    userTimezone, // Current user's IANA timezone string from their profile
  } = useMentorshipData();

  const { roles } = useAuth();
  const isInternal = roles?.includes(USER_ROLES.CC_INTERNAL);

  const { summary, isPersonalSummaryLoading, fetchPersonalSummary } =
    useWorkActivityData({ enabled: isInternal });

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
        matchResult={matchResult}
        matchResultRoundName={matchResultRoundName}
        canViewMatch={canViewMatch}
      />

      {/* Mentorship participant card */}
      <MentorshipParticipantsCard
        userTimezone={userTimezone}
        roundSelectionData={roundSelectionData}
        selectedRoundId={selectedRoundId}
        onRoundChange={handleRoundChange}
        isParticipantCardLoading={isParticipantCardLoading}
        participantDetails={participantDetails}
        refreshMeetings={refreshMeetings}
      />

      {/* Work Activity Data Card */}
      {isInternal && (
        <WorkActivityDataCard
          initialData={summary}
          isLoading={isPersonalSummaryLoading}
          onSearch={({ startDate, endDate }) =>
            fetchPersonalSummary(startDate, endDate)
          }
        />
      )}
    </div>
  );
};

export default PersonalDashboard;
