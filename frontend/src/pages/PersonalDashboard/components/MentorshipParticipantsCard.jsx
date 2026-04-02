import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useState } from "react";
import { GraduationCap, User, Plus } from "lucide-react";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import MeetingSubmissionModal from "@/pages/PersonalDashboard/components/MeetingSubmissionModal";
import MeetingOverviewCard from "@/pages/PersonalDashboard/components/MeetingOverviewCard";
import { MentorshipParticipantRoles } from "@/constants/MentorshipParticipantRoles";
import { MentorshipRoundStatus } from "@/constants/MentorshipRoundStatus";

/**
 * Displays the current user's mentorship participation for a selected round.
 *
 * - Show role, round details, and per-partner meeting overview via MeetingOverviewCard.
 * - Provide a round selector to switch between rounds.
 * - Allow mentees to open the meeting submission modal.
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
  const [isMeetingModalOpen, setIsMeetingModalOpen] = useState(false);

  const hasParticipation =
    !isParticipantCardLoading &&
    partnerMeetingOverview?.length > 0 &&
    participantRole;
  const getRoleIcon = (role) => {
    return role?.toLowerCase() === MentorshipParticipantRoles.MENTOR ? (
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
            {participantRole?.toLowerCase() ===
              MentorshipParticipantRoles.MENTEE && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => setIsMeetingModalOpen(true)}
                disabled={
                  !hasParticipation ||
                  roundInfo?.status === MentorshipRoundStatus.COMPLETED
                }
              >
                <Plus className="h-4 w-4 mr-2" />
                Submit Meeting Info
              </Button>
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
                    {roundInfo?.timeline?.matchNotificationAt ||
                      roundInfo?.timeline?.promotionStartAt}{" "}
                    to {roundInfo?.timeline?.meetingsCompletionDeadlineAt}
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
                    {overview.preferredName}
                  </p>
                  <MeetingOverviewCard
                    overview={overview}
                    userTimezone={userTimezone}
                    showMeetingList={
                      roundInfo?.status === MentorshipRoundStatus.ACTIVE
                    }
                  />
                </div>
              ))}
            </div>
          </>
        )}
      </CardContent>

      <MeetingSubmissionModal
        open={isMeetingModalOpen}
        onOpenChange={setIsMeetingModalOpen}
        roundId={selectedRoundId}
        userTimezone={userTimezone}
        onSuccess={() => {
          setIsMeetingModalOpen(false);
          refreshMeetings();
        }}
      />
    </Card>
  );
}
