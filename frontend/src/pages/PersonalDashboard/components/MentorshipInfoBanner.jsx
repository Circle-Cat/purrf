import { Link } from "react-router-dom";
import { Info } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import StageProgress from "@/components/common/StageProgress";
import { ROUTE_PATHS } from "@/constants/RoutePaths";
import { cn } from "@/lib/utils";
import MentorshipRegistrationDialog from "@/pages/PersonalDashboard/components/MentorshipRegistrationDialog";
import MatchingResultDialog from "@/pages/PersonalDashboard/components/MatchingResultDialog";
import { MENTORSHIP_BANNER_COPY as COPY } from "@/pages/PersonalDashboard/components/mentorshipBannerCopy";
import {
  BannerAction,
  BannerKind,
  BannerTone,
  mentorshipBannerState,
} from "@/pages/PersonalDashboard/utils/mentorshipBannerState";

export const TRAINING_PATH = `${ROUTE_PATHS.PROFILE}#training`;

const NEXT_BOX_TONE = {
  [BannerTone.NORMAL]: "bg-purple-50 text-slate-900",
  [BannerTone.AMBER]: "bg-amber-50 text-amber-900",
  [BannerTone.MUTED]: "bg-slate-100 text-slate-700",
};

const ACTION_TONE = {
  [BannerTone.NORMAL]: "bg-[#6035F3] text-white hover:bg-[#4B23D1]",
  [BannerTone.AMBER]: "bg-amber-700 text-white hover:bg-amber-800",
  [BannerTone.MUTED]: "bg-slate-600 text-white hover:bg-slate-700",
};

/**
 * Mentorship banner for the personal dashboard. It follows the round taking
 * registrations: a Register, Training, Matching progress bar, one "Next"
 * line with at most one action, and the registration entry points.
 *
 * @param {Object} props - Component props.
 * @param {boolean} props.isLoading - Whether the data it reads is still
 *   loading; nothing renders until it is not.
 * @param {string|number|null} props.regRoundId - The round in the
 *   registration slot.
 * @param {string} props.regRoundName - That round's display name.
 * @param {Object|null} props.registration - The user's registration for the
 *   round taking registrations, or the round-level answer when they have
 *   not registered.
 * @param {boolean} props.isRegistrationOpen - Whether registration is open.
 * @param {string|null} props.registrationDeadlineAt - The shared
 *   registration and onboarding training deadline.
 * @param {boolean} props.isTrainingDone - Whether the viewer's onboarding
 *   training is done.
 * @param {{sortedRounds: Array<Object>}} props.roundSelectionData - Every
 *   round, with timelines.
 * @param {string} props.userTimezone - The viewer's IANA zone.
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
  isLoading = false,
  regRoundId = null,
  regRoundName = "",
  registration,
  isRegistrationOpen,
  registrationDeadlineAt = null,
  isTrainingDone = false,
  roundSelectionData,
  userTimezone,
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
  if (isLoading) return null;

  const rounds = roundSelectionData?.sortedRounds ?? [];
  const regRound =
    regRoundId === null
      ? null
      : rounds.find((r) => String(r.id) === String(regRoundId));

  const state = mentorshipBannerState({
    now: new Date(),
    timezone: userTimezone,
    regRoundId,
    regRoundName: regRoundName || registration?.roundName || "",
    regTimeline: regRound?.timeline ?? null,
    isRegistrationOpen: Boolean(isRegistrationOpen),
    registrationDeadlineAt,
    isRegistered: Boolean(registration?.isRegistered),
    isTrainingDone,
    canViewMatch: Boolean(canViewMatch),
    matchStatus: matchResult?.currentStatus ?? null,
    rounds,
  });

  const isRoundShown = state.kind !== BannerKind.NO_ROUND;
  const goal = isRoundShown ? registration?.roundPreferences?.goal || "" : "";

  const renderRegistrationDialog = (entry, triggerClassName) => (
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
      triggerClassName={triggerClassName}
    />
  );

  // A registration settles the round's role; its entry stays reachable
  // (Update or View) for as long as the round is shown.
  const headerEntries =
    registeredRole && isRoundShown
      ? registrationEntries.filter((entry) => entry.role === registeredRole)
      : [];

  const actionClass = ACTION_TONE[state.tone];
  let action = null;
  if (state.action === BannerAction.REGISTER) {
    action = registrationEntries
      .filter((entry) => entry.isOpen)
      .map((entry) => renderRegistrationDialog(entry, actionClass));
  } else if (state.action === BannerAction.TRAINING) {
    action = (
      <Button asChild className={actionClass}>
        <Link to={TRAINING_PATH}>{COPY.goToTraining}</Link>
      </Button>
    );
  } else if (state.action === BannerAction.MATCH_RESULT) {
    action = (
      <MatchingResultDialog
        roundName={matchResultRoundName}
        canViewMatch={canViewMatch}
        matchData={matchResult}
      />
    );
  }

  return (
    <Card
      className="border-gray-200 bg-white shadow-sm"
      data-testid="mentorship-banner"
      data-kind={state.kind}
    >
      <CardHeader className="pb-0">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div className="space-y-1">
            <CardTitle className="text-xl font-bold leading-none text-purple-900">
              {state.title}
            </CardTitle>
            {goal && (
              <p className="m-0 text-sm text-gray-700">
                <span className="font-semibold text-gray-900">
                  {COPY.goalLabel}
                </span>{" "}
                {goal}
              </p>
            )}
          </div>
          {headerEntries.length > 0 && (
            <div className="flex flex-wrap gap-2">
              {headerEntries.map((entry) => renderRegistrationDialog(entry))}
            </div>
          )}
        </div>
      </CardHeader>
      <CardContent className="space-y-4 pt-0">
        {state.steps && (
          <StageProgress
            steps={state.steps}
            tone={state.tone}
            label={COPY.progressLabel}
            narrowText={COPY.narrowStep}
          />
        )}

        <div
          data-testid="mentorship-banner-next"
          data-tone={state.tone}
          className={cn(
            "flex flex-col gap-3 rounded-lg px-4 py-3 sm:flex-row sm:flex-wrap sm:items-center sm:justify-between",
            NEXT_BOX_TONE[state.tone],
          )}
        >
          <p className="m-0 min-w-0 flex-1 text-sm leading-relaxed">
            {state.lead && (
              <strong className="font-semibold">{state.lead}</strong>
            )}
            {state.lead && " "}
            {state.next}
          </p>
          {action && <div className="flex flex-wrap gap-2">{action}</div>}
        </div>

        {state.showProfileLine && (
          <div className="flex flex-col gap-1 px-1 sm:flex-row sm:items-center sm:justify-between sm:gap-3">
            <p className="m-0 flex items-start gap-2 text-xs text-slate-600">
              <Info className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
              <span>{COPY.profileLine}</span>
            </p>
            <Link
              to={ROUTE_PATHS.PROFILE}
              className="shrink-0 text-xs font-medium text-[#6035F3] no-underline hover:underline"
            >
              {COPY.updateProfile}
            </Link>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
