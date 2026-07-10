import MentorshipInfoBanner from "@/pages/PersonalDashboard/components/MentorshipInfoBanner";
import { WorkActivityDataCard } from "@/pages/PersonalDashboard/components/WorkActivityDataCard";
import MentorshipParticipantsCard from "@/pages/PersonalDashboard/components/MentorshipParticipantsCard";
import { useMentorshipData } from "@/pages/PersonalDashboard/hooks/useMentorshipData";
import { useWorkActivityData } from "@/pages/PersonalDashboard/hooks/useWorkActivityData";
import MyApplicationsCard from "@/pages/PersonalDashboard/components/MyApplicationsCard";
import { useMyApplications } from "@/pages/PersonalDashboard/hooks/useMyApplications";
import { useAuth } from "@/context/auth";
import { PERMISSIONS } from "@/constants/Permissions";
import { MentorshipRoundStatus } from "@/constants/MentorshipRoundStatus";
import { GoogleMeetingControl } from "@/pages/PersonalDashboard/components/GoogleMeetingControl";

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
    applications,
    isLoading: isApplicationsLoading,
    loadError: applicationsLoadError,
    load: loadApplications,
    hiredMentorshipRole,
  } = useMyApplications();

  // Only show the mentorship section, and only start fetching mentorship
  // data, once we've actually confirmed a hired mentorship role — not
  // while the applications fetch is still loading or has errored. This is
  // a deliberate reversal of the previous fail-open behavior: a slow/failed
  // fetch now hides the section (the user can retry via My Applications'
  // own retry button) rather than firing a wasted mentorship-data fetch.
  const showMentorshipSection =
    !isApplicationsLoading &&
    !applicationsLoadError &&
    hiredMentorshipRole !== null;

  const {
    registration, // Registration data for the current or most recent round
    isRegistrationOpen, // Whether the registration period is currently open
    isFeedbackEnabled, // Whether the feedback phase is currently active
    feedbackRoundId, // Round ID for which feedback is currently open
    feedbackRoundName, // Display name of the feedback round
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
  } = useMentorshipData({ enabled: showMentorshipSection });

  const { permissions } = useAuth();
  const canViewActivitySummary = permissions?.includes(
    PERMISSIONS.DASHBOARD_ACTIVITY_SUMMARY_READ,
  );

  const { summary, isPersonalSummaryLoading, fetchPersonalSummary } =
    useWorkActivityData({ enabled: canViewActivitySummary });

  const currentSelectedRound = roundSelectionData?.sortedRounds?.find(
    (round) => Number(round.id) === Number(selectedRoundId),
  );

  const isCurrentRoundActive =
    currentSelectedRound?.status === MentorshipRoundStatus.ACTIVE;

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

        <GoogleMeetingControl
          meetingRoundId={isCurrentRoundActive ? Number(selectedRoundId) : null}
          onRefresh={refreshMeetings}
        />
      </div>

      {/* My Applications card */}
      <MyApplicationsCard
        applications={applications}
        isLoading={isApplicationsLoading}
        loadError={applicationsLoadError}
        onRetry={loadApplications}
      />

      {showMentorshipSection && (
        <>
          {/* Mentorship information banner */}
          <MentorshipInfoBanner
            registration={registration}
            isRegistrationOpen={isRegistrationOpen}
            isFeedbackEnabled={isFeedbackEnabled}
            feedbackRoundId={feedbackRoundId}
            feedbackRoundName={feedbackRoundName}
            hiredMentorshipRole={hiredMentorshipRole}
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
        </>
      )}

      {/* Work Activity Data Card */}
      {canViewActivitySummary && (
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
