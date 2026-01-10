import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Target, ExternalLink } from "lucide-react";
import MentorshipRegistrationDialog from "@/pages/PersonalDashboard/components/MentorshipRegistrationDialog";

export default function MentorshipInfoBanner({
  registration,
  isRegistrationOpen,
  isFeedbackEnabled,
  onSaveRegistration,
  pastPartners,
  isPartnersLoading,
  onLoadPastPartners,
  refreshRegistration,
}) {
  // Do not render the banner if there is no registration data,
  // registration is closed, and feedback is not enabled
  if (!isRegistrationOpen && !registration && !isFeedbackEnabled) return null;

  const displayGoal = registration?.roundPreferences?.goal || "";

  return (
    <Card className="border-gray-200 shadow-sm bg-gradient-to-r from-purple-50 to-white">
      <CardContent className="pt-6">
        <div className="space-y-4">
          {/* Only render this section when a goal is available */}
          {displayGoal && (
            <div className="flex items-start gap-3">
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

            {/* Feedback button */}
            <Button
              variant="outline"
              className="border-[#6035F3] text-[#6035F3] hover:bg-purple-50 disabled:opacity-50"
              disabled={!isFeedbackEnabled}
              asChild={isFeedbackEnabled}
            >
              {isFeedbackEnabled ? (
                <a
                  href="https://forms.google.com/mentorship-feedback"
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  <ExternalLink className="h-4 w-4 mr-2" />
                  Submit Mentorship Feedback
                </a>
              ) : (
                <span className="flex items-center">
                  <ExternalLink className="h-4 w-4 mr-2" />
                  Submit Mentorship Feedback
                </span>
              )}
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
