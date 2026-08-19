import { Card, CardContent, CardTitle, CardHeader } from "@/components/ui/card";
import { Target } from "lucide-react";
import MentorshipRegistrationDialog from "@/pages/PersonalDashboard/components/MentorshipRegistrationDialog";
import MatchingResultDialog from "@/pages/PersonalDashboard/components/MatchingResultDialog";

/**
 * Mentorship banner for the personal dashboard: the round's name, the goal
 * of an existing registration, and one registration entry point per role
 * the user may act on.
 *
 * @param {Object} props - Component props.
 * @param {Object|null} props.registration - The user's registration for the
 *   round taking registrations, or the round-level answer when they have
 *   not registered.
 * @param {boolean} props.isRegistrationOpen - Whether any of the user's
 *   roles still has an open window.
 * @param {boolean} props.isFeedbackEnabled - Whether the feedback phase is active.
 * @param {Array<{role: string, deadlineAt: string|null, isOpen: boolean}>} props.registrationEntries -
 *   One entry per role the user may register under.
 * @param {"mentor"|"mentee"|null} props.registeredRole - The role an existing
 *   registration settled on, or null when there is none.
 * @param {(data: Object) => Promise<any>} props.onSaveRegistration - Submits a registration.
 * @param {(role: string) => Promise<Object|null>} props.loadRegistrationForRole -
 *   Fetches one role's form prefill.
 * @param {Array<Object>} props.pastPartners - The user's past partners.
 * @param {boolean} props.isPartnersLoading - Whether the partner list is loading.
 * @param {() => Promise<void>} props.onLoadPastPartners - Loads the partner list.
 * @param {() => Promise<void>} props.refreshRegistration - Refreshes the registration.
 * @param {Object|null} props.matchResult - The matching result data.
 * @param {string} props.matchResultRoundName - Round name the match belongs to.
 * @param {boolean} props.canViewMatch - Whether the match result is visible.
 * @returns {JSX.Element|null}
 */
export default function MentorshipInfoBanner({
  registration,
  isRegistrationOpen,
  isFeedbackEnabled,
  registrationEntries = [],
  registeredRole,
  onSaveRegistration,
  loadRegistrationForRole,
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

  // Entries a registered user can still act on, plus -- when they have not
  // registered -- only the roles whose window is still open. A closed role
  // offers nothing to fill in and nothing to read back.
  const visibleEntries = registeredRole
    ? registrationEntries
    : registrationEntries.filter((entry) => entry.isOpen);

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
            {/* One registration / view dialog per actionable role */}
            {visibleEntries.map((entry) => (
              <MentorshipRegistrationDialog
                key={entry.role}
                role={entry.role}
                currentRegistration={registration}
                loadRegistrationForRole={loadRegistrationForRole}
                allPastPartners={pastPartners}
                isPartnersLoading={isPartnersLoading}
                loadPastPartners={onLoadPastPartners}
                refreshRegistration={refreshRegistration}
                isLocked={!entry.isOpen}
                onSave={onSaveRegistration}
              />
            ))}

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
            {/* Feedback now lives on MentorshipParticipantsCard, next to
                Submit Meeting Info, so it follows the round selected there. */}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
