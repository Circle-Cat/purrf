import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { addDays, addMonths, isAfter, isBefore, subMonths } from "date-fns";
import { formatInTz, formatDateTimeWithZone } from "@/utils/dateTime";
import { useFeatureFlags } from "@/hooks/useFeatureFlags";
import { FEATURE_FLAGS } from "@/constants/FeatureFlags";
import { GraduationCap, User } from "lucide-react";
import { toast } from "sonner";
import { deleteMeeting } from "@/api/meetingApi";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import MeetingManagementDialog from "@/pages/PersonalDashboard/components/MeetingManagementDialog";
import { userDisplayName } from "@/utils/userName";
import MeetingOverviewCard from "@/pages/PersonalDashboard/components/MeetingOverviewCard";
import MentorshipFeedbackDialog from "@/pages/PersonalDashboard/components/MentorshipFeedbackDialog";
import { MentorshipParticipantRoles } from "@/constants/MentorshipParticipantRoles";
import { MentorshipRoundStatus } from "@/constants/MentorshipRoundStatus";

/**
 * Displays the current user's mentorship participation for a selected round.
 *
 * - Show role, round details, and per-partner meeting overview via MeetingOverviewCard.
 * - Provide a round selector to switch between rounds.
 * - Host the meeting entry point, which sits beside the round selector that
 *   governs it rather than elsewhere on the page.
 *
 * @param {{
 *   roundSelectionData: { sortedRounds: Array },
 *   selectedRoundId: string | number | null,
 *   onRoundChange: (id: string) => void,
 *   isParticipantCardLoading: boolean,
 *   participantDetails: {
 *     roundInfo: Object | null,
 *     partnerMeetingOverview: Array,
 *     participantRole: string | null
 *   },
 *   refreshMeetings: () => void
 * }} props
 */
export default function MentorshipParticipantsCard({
  roundSelectionData,
  selectedRoundId,
  onRoundChange,
  isParticipantCardLoading,
  participantDetails,
  refreshMeetings,
  userTimezone,
}) {
  const { roundInfo, partnerMeetingOverview, participantRole } =
    participantDetails || {};
  const {
    [FEATURE_FLAGS.MANUAL_SUBMIT_MEETING]: manualSubmitMeeting,
    [FEATURE_FLAGS.CREATE_GOOGLE_MEETING]: createGoogleMeeting,
  } = useFeatureFlags();
  const isMentee =
    participantRole?.toLowerCase() === MentorshipParticipantRoles.MENTEE;
  const canSubmitMeeting = isMentee && manualSubmitMeeting;

  const formatDt = (utcStr) => formatInTz(utcStr, userTimezone, "yyyy-MM-dd");

  const hasParticipation =
    !isParticipantCardLoading &&
    partnerMeetingOverview?.length > 0 &&
    participantRole;

  // A pairing that ended -- the mentor changed mid-round, or the partner left
  // the program -- still belongs on the card: the meetings held with them are
  // this user's participation. It is not somewhere new meetings can go, so
  // only the live pairings are candidates for submission.
  const livePairings = (partnerMeetingOverview || []).filter(
    (overview) => overview.isActive !== false,
  );

  // The submission modal is one per round rather than one per partner, so it
  // can only name a partner while there is exactly one to name -- a mentee and
  // their current mentor. Any other count leaves the target pair ambiguous, so
  // submission is withheld rather than guessing which partner the meeting was
  // held with.
  const submissionPartnerId =
    livePairings.length === 1 ? livePairings[0].partnerId : null;

  // Logging stays open for a day past the meetings deadline, so meetings held
  // right up against it can still be recorded. Booking a new meeting needs a
  // round that is still running, which is a different question -- keeping the
  // two reasons apart is what lets the entry point stay reachable for one
  // while the other is closed.
  const deadline = roundInfo?.timeline?.meetingsCompletionDeadlineAt;
  const isLoggingClosed = deadline
    ? isAfter(new Date(), addDays(new Date(deadline), 1))
    : roundInfo?.status === MentorshipRoundStatus.COMPLETED;
  const logUnavailableReason = isLoggingClosed
    ? "Logging meetings for this round has closed."
    : !hasParticipation || submissionPartnerId == null
      ? "No single active pairing to log a meeting against."
      : null;

  const selectedRound = roundSelectionData?.sortedRounds?.find(
    (round) => Number(round.id) === Number(selectedRoundId),
  );
  const scheduleUnavailableReason =
    selectedRound?.status === MentorshipRoundStatus.ACTIVE
      ? null
      : "No active mentorship round";

  // Feedback opens halfway through the round rather than after all meetings are
  // done, so participants can write it while the round is still fresh. Both
  // anchors are optional in the round form, so each falls back to a month
  // either side of the (required) meetings deadline.
  const meetingsEnd = deadline ? new Date(deadline) : null;
  const feedbackOpensAt = roundInfo?.timeline?.meetingLogReminderAt
    ? new Date(roundInfo.timeline.meetingLogReminderAt)
    : meetingsEnd
      ? subMonths(meetingsEnd, 1)
      : null;
  const feedbackClosesAt = roundInfo?.timeline?.feedbackDeadlineAt
    ? new Date(roundInfo.timeline.feedbackDeadlineAt)
    : meetingsEnd
      ? addMonths(meetingsEnd, 1)
      : null;

  // Past the closing date the dialog stays reachable but read-only, so people
  // can still look back at what they submitted.
  const showFeedback = Boolean(
    hasParticipation &&
    feedbackOpensAt &&
    !isBefore(new Date(), feedbackOpensAt),
  );
  const isFeedbackEditable =
    !feedbackClosesAt || !isAfter(new Date(), feedbackClosesAt);
  const feedbackDeadlineText = feedbackClosesAt
    ? formatDateTimeWithZone(feedbackClosesAt.toISOString(), userTimezone)
    : null;

  // Cancelling is offered on the same terms as booking: both go through
  // Google, so the flag that gates creating a meeting gates calling one off.
  const canCancelMeetings = Boolean(createGoogleMeeting);

  /**
   * Cancel one meeting held with a partner, then refresh the round's meetings
   * so the list reflects what is left.
   *
   * @param {string | number} partnerId - Partner the meeting was booked with.
   * @param {{meetingId: string}} meeting - Meeting to cancel.
   * @returns {Promise<void>}
   */
  const handleCancelMeeting = async (partnerId, meeting) => {
    try {
      await deleteMeeting(meeting.meetingId, selectedRoundId, partnerId);
      toast.success("Meeting cancelled successfully!");
      await refreshMeetings?.();
    } catch (error) {
      console.error("Failed to cancel meeting:", error);
      toast.error("Failed to cancel the meeting.");
    }
  };

  const getRoleIcon = (participantRole) => {
    return participantRole?.toLowerCase() ===
      MentorshipParticipantRoles.MENTOR ? (
      <GraduationCap className="h-4 w-4" />
    ) : (
      <User className="h-4 w-4" />
    );
  };

  return (
    <Card className="mt-6">
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle>Mentorship Participation</CardTitle>
          <div className="flex items-center gap-2">
            <MeetingManagementDialog
              roundId={selectedRoundId}
              canSchedule={Boolean(createGoogleMeeting)}
              scheduleUnavailableReason={scheduleUnavailableReason}
              canLogPast={canSubmitMeeting}
              logPartnerId={submissionPartnerId}
              logUnavailableReason={logUnavailableReason}
              userTimezone={userTimezone}
              onBooked={refreshMeetings}
              onLogged={refreshMeetings}
            />
            {showFeedback && (
              <MentorshipFeedbackDialog
                roundId={selectedRoundId}
                roundName={roundInfo?.name}
                isEditable={isFeedbackEditable}
                feedbackDeadlineText={feedbackDeadlineText}
              />
            )}
            <Select
              value={selectedRoundId?.toString() || ""}
              onValueChange={onRoundChange}
              disabled={false}
            >
              <SelectTrigger className="w-[250px] bg-gray-50 border-none">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {roundSelectionData?.sortedRounds?.map((round) => (
                  <SelectItem key={round.id} value={round.id.toString()}>
                    {round.name}
                    {round.status === MentorshipRoundStatus.ACTIVE
                      ? " (Current)"
                      : ""}
                    {round.status === MentorshipRoundStatus.UPCOMING
                      ? " (Upcoming)"
                      : ""}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>
      </CardHeader>

      <CardContent>
        {isParticipantCardLoading ? (
          <div className="py-10 text-center text-gray-500">
            Loading participation data...
          </div>
        ) : !hasParticipation ? (
          <div className="text-center py-8 text-gray-500">
            <GraduationCap className="h-12 w-12 mx-auto mb-3 text-gray-400" />
            {participantDetails?.isRegistered
              ? "You are registered for this round but have not been matched yet."
              : "You have not participated in the mentorship program in this round."}
          </div>
        ) : (
          <>
            <div className="flex items-start justify-between pb-6 border-b">
              <div className="flex-1">
                <h4 className="flex items-center gap-2 mb-2 text-lg font-semibold">
                  {getRoleIcon(participantRole)}
                  {roundInfo?.name}
                </h4>
                <div className="space-y-1 text-sm text-gray-600">
                  <p>
                    <span className="font-medium">Role:</span>{" "}
                    {participantRole
                      ? participantRole.charAt(0).toUpperCase() +
                        participantRole.slice(1).toLowerCase()
                      : null}
                  </p>
                  <p>
                    <span className="font-medium">Duration:</span>{" "}
                    {formatDt(
                      roundInfo?.timeline?.matchNotificationAt ??
                        roundInfo?.timeline?.promotionStartAt,
                    )}{" "}
                    to{" "}
                    {formatDt(
                      roundInfo?.timeline?.meetingsCompletionDeadlineAt,
                    )}{" "}
                    {userTimezone}
                  </p>
                </div>
              </div>
              <div>
                {roundInfo?.status === MentorshipRoundStatus.ACTIVE && (
                  <Badge variant="default">Active</Badge>
                )}
                {roundInfo?.status === MentorshipRoundStatus.COMPLETED && (
                  <Badge variant="secondary">Completed</Badge>
                )}
              </div>
            </div>

            <div className="divide-y">
              {partnerMeetingOverview.map((overview) => (
                <div key={overview.partnerId} className="py-6 last:pb-0">
                  <p className="text-sm text-gray-600 mb-2">
                    <span className="font-medium">
                      {overview.participantRole?.toLowerCase() ===
                      MentorshipParticipantRoles.MENTEE
                        ? "Mentor"
                        : "Mentee"}
                      :
                    </span>{" "}
                    {overview.partnerEmail ? (
                      <a
                        href={`mailto:${overview.partnerEmail}`}
                        className="text-primary underline hover:opacity-80"
                      >
                        {userDisplayName(overview)}
                      </a>
                    ) : (
                      userDisplayName(overview)
                    )}
                    {overview.isActive === false && (
                      <Badge
                        variant="secondary"
                        className="ml-2 font-normal align-middle"
                      >
                        Ended
                      </Badge>
                    )}
                  </p>
                  <MeetingOverviewCard
                    overview={overview}
                    userTimezone={userTimezone}
                    showMeetingList={
                      roundInfo?.status === MentorshipRoundStatus.ACTIVE
                    }
                    canDelete={canCancelMeetings}
                    onDeleteMeeting={(meeting) =>
                      handleCancelMeeting(overview.partnerId, meeting)
                    }
                  />
                </div>
              ))}
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}
