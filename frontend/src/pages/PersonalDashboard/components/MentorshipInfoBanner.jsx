import { Card, CardContent, CardTitle, CardHeader } from "@/components/ui/card";
import { Target } from "lucide-react";
import MentorshipRegistrationDialog from "@/pages/PersonalDashboard/components/MentorshipRegistrationDialog";
import MatchingResultDialog from "@/pages/PersonalDashboard/components/MatchingResultDialog";
import MentorshipFeedbackDialog from "@/pages/PersonalDashboard/components/MentorshipFeedbackDialog";

export default function MentorshipInfoBanner({
  registration,
  isRegistrationOpen,
  isFeedbackEnabled,
  feedbackRoundId,
  feedbackRoundName,
  onSaveRegistration,
  pastPartners,
  isPartnersLoading,
  onLoadPastPartners,
  refreshRegistration,
  matchResult,
  matchResultRoundName,
  canViewMatch,
}) {
  // Do not render the banner if there is no registration data,
  // registration is closed, and feedback is not enabled
  if (!isRegistrationOpen && !registration && !isFeedbackEnabled) return null;

  const displayGoal = registration?.roundPreferences?.goal || "";

  return (
    <Card className="border-gray-200 shadow-sm bg-gradient-to-r from-purple-50 to-white">
      <CardHeader className="pb-0">
        <CardTitle className="text-xl font-bold text-purple-900 leading-none pb-0">
          {registration?.roundName}
        </CardTitle>
      </CardHeader>
      <CardContent className="pt-0">
        <div className="space-y-4 pt-0">
          {/* Only render this section when a goal is available */}
          {displayGoal && (
            <div className="flex items-start gap-3 pt-0">
              <div className="p-2 bg-purple-100 rounded-lg shrink-0">
                <Target className="h-5 w-5 text-[#6035F3]" />
              </div>
              <div className="flex-1">
                <h3 className="font-semibold text-gray-900 mb-1">
                  Current Mentorship Goal
                </h3>
                <p className="text-gray-700 text-sm leading-relaxed">
                  {displayGoal}
                </p>
              </div>
            </div>
          )}

          {/* Action buttons */}
          <div className="flex flex-wrap items-center gap-3 pt-2">
            {/* Registration / view dialog button */}
            <MentorshipRegistrationDialog
              currentRegistration={registration}
              allPastPartners={pastPartners}
              isPartnersLoading={isPartnersLoading}
              loadPastPartners={onLoadPastPartners}
              refreshRegistration={refreshRegistration}
              isLocked={!isRegistrationOpen}
              onSave={onSaveRegistration}
            />

            {/* Render these buttons only when the user is registered for the current round */}
            {registration?.isRegistered && (
              <>
                {/* View Matching result */}
                <MatchingResultDialog
                  roundName={matchResultRoundName}
                  canViewMatch={canViewMatch}
                  matchData={matchResult}
                />
              </>
            )}

            {/* Feedback dialog button */}
            <MentorshipFeedbackDialog
              roundId={feedbackRoundId}
              roundName={feedbackRoundName}
              isFeedbackEnabled={isFeedbackEnabled}
            />
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
