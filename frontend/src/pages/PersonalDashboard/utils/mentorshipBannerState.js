import { formatInTz } from "@/utils/dateTime";
import { MatchStatus } from "@/constants/matchStatus";
import { MENTORSHIP_BANNER_COPY as COPY } from "@/pages/PersonalDashboard/components/mentorshipBannerCopy";

const DAY_MS = 24 * 60 * 60 * 1000;
const SOON_MS = 3 * DAY_MS;

export const BannerKind = Object.freeze({
  NO_ROUND: "noRound",
  REGISTER: "register",
  REGISTRATION_CLOSED: "registrationClosed",
  TRAINING: "training",
  TRAINING_OVERDUE: "trainingOverdue",
  AWAITING_MATCHES: "awaitingMatches",
  MATCHED: "matched",
  UNMATCHED: "unmatched",
  PAIRING_ENDED: "pairingEnded",
  PARTICIPATION_ENDED: "participationEnded",
  NOT_TAKING_PART: "notTakingPart",
  WITHDRAWN: "withdrawn",
  RESULT_NOT_READY: "resultNotReady",
});

export const BannerAction = Object.freeze({
  REGISTER: "register",
  TRAINING: "training",
  MATCH_RESULT: "matchResult",
});

export const BannerTone = Object.freeze({
  NORMAL: "normal",
  AMBER: "amber",
  MUTED: "muted",
});

export const StepState = Object.freeze({
  DONE: "done",
  CURRENT: "current",
  FAILED: "failed",
  UPCOMING: "upcoming",
});

const toTime = (iso) => {
  if (!iso) return null;
  const t = new Date(iso).getTime();
  return Number.isNaN(t) ? null : t;
};

/** "Nov 26" in the viewer's zone. */
const formatDay = (iso, tz) => formatInTz(iso, tz, "MMM d");

/** Whole calendar days from `now` to `iso`, counted in the viewer's zone. */
const calendarDaysUntil = (now, iso, tz) => {
  const [y1, m1, d1] = formatInTz(now.toISOString(), tz, "yyyy-M-d")
    .split("-")
    .map(Number);
  const [y2, m2, d2] = formatInTz(iso, tz, "yyyy-M-d").split("-").map(Number);
  return Math.round(
    (Date.UTC(y2, m2 - 1, d2) - Date.UTC(y1, m1 - 1, d1)) / DAY_MS,
  );
};

/**
 * The earliest round whose promotion has not started yet. Round status and
 * the active-round slot describe other things, so only the timeline counts.
 */
const findNextRound = (rounds, nowMs) =>
  (rounds ?? [])
    .filter((r) => {
      const start = toTime(r?.timeline?.promotionStartAt);
      return start !== null && start > nowMs;
    })
    .sort(
      (a, b) =>
        toTime(a.timeline.promotionStartAt) -
        toTime(b.timeline.promotionStartAt),
    )[0] ?? null;

const buildSteps = ({ registerState, isRegistered, isTrainingDone }) => {
  const steps = [
    {
      key: "register",
      label: COPY.steps.register,
      state: registerState ?? (isRegistered ? StepState.DONE : null),
    },
    {
      key: "training",
      label: COPY.steps.training,
      state: isTrainingDone ? StepState.DONE : null,
    },
    { key: "matching", label: COPY.steps.matching, state: null },
  ];
  const hasFailed = steps.some((s) => s.state === StepState.FAILED);
  let currentAssigned = hasFailed;
  return steps.map((step) => {
    if (step.state) return step;
    if (!currentAssigned) {
      currentAssigned = true;
      return { ...step, state: StepState.CURRENT };
    }
    return { ...step, state: StepState.UPCOMING };
  });
};

const noRound = ({ rounds, nowMs, tz }) => {
  const next = findNextRound(rounds, nowMs);
  return {
    kind: BannerKind.NO_ROUND,
    title: COPY.fallbackTitle,
    steps: null,
    tone: BannerTone.NORMAL,
    lead: COPY.leadNext,
    next: next
      ? COPY.nextRoundScheduled(
          next.name,
          formatDay(next.timeline.promotionStartAt, tz),
        )
      : COPY.nextRoundUnscheduled,
    action: null,
    showProfileLine: false,
    showRegistrationEntry: false,
  };
};

/**
 * Derives what the mentorship banner shows from the round taking
 * registrations and where the viewer stands in it.
 *
 * @param {Object} params
 * @param {Date} params.now - The current instant.
 * @param {string} params.timezone - The viewer's IANA zone for dates.
 * @param {string|number|null} params.regRoundId - The round in the
 *   registration slot, or null when none is.
 * @param {string} params.regRoundName - That round's display name.
 * @param {Object|null} params.regTimeline - That round's timeline.
 * @param {boolean} params.isRegistrationOpen - Whether registration is open.
 * @param {string|null} params.registrationDeadlineAt - Shared deadline for
 *   registration and onboarding training.
 * @param {boolean} params.isRegistered - Whether the viewer registered.
 * @param {boolean} params.isTrainingDone - Whether their onboarding training
 *   is done.
 * @param {boolean} params.canViewMatch - Whether matches are viewable now.
 * @param {string|null} params.matchStatus - The viewer's match status.
 * @param {Array<{isActive?: boolean|null}>} [params.partners] - The viewer's
 *   partners in the round, as the match result reports them.
 * @param {Array<Object>} params.rounds - Every round, with timelines.
 * @returns {{
 *   kind: string,
 *   title: string,
 *   steps: Array<{key: string, label: string, state: string}>|null,
 *   tone: string,
 *   lead: string|null,
 *   next: string,
 *   action: string|null,
 *   showProfileLine: boolean,
 *   showRegistrationEntry: boolean,
 * }}
 */
export function mentorshipBannerState({
  now,
  timezone,
  regRoundId,
  regRoundName,
  regTimeline,
  isRegistrationOpen,
  registrationDeadlineAt,
  isRegistered,
  isTrainingDone,
  canViewMatch,
  matchStatus,
  partners = [],
  rounds,
}) {
  const tz = timezone;
  const nowMs = now.getTime();

  if (regRoundId === null || regRoundId === undefined) {
    return noRound({ rounds, nowMs, tz });
  }

  const promotionStartMs = toTime(regTimeline?.promotionStartAt);
  if (
    !isRegistrationOpen &&
    promotionStartMs !== null &&
    nowMs < promotionStartMs
  ) {
    return noRound({ rounds, nowMs, tz });
  }

  const title = regRoundName || COPY.fallbackTitle;
  const deadlineAt =
    registrationDeadlineAt ?? regTimeline?.onboardingDeadlineAt ?? null;
  const deadlineMs = toTime(deadlineAt);
  const matchAtIso = regTimeline?.matchNotificationAt ?? null;
  const matchAtMs = toTime(matchAtIso);
  const matchDatePassed = matchAtMs !== null && nowMs >= matchAtMs;
  const isDueSoon =
    deadlineMs !== null && deadlineMs > nowMs && deadlineMs - nowMs < SOON_MS;
  const deadlineDay = deadlineAt ? formatDay(deadlineAt, tz) : null;
  const inDays = () => COPY.inDays(calendarDaysUntil(now, deadlineAt, tz));

  // Once matching is done, editing the profile no longer changes anything
  // for this round, whatever the viewer's status.
  const base = {
    title,
    lead: COPY.leadNext,
    action: null,
    showProfileLine: !matchDatePassed,
    showRegistrationEntry: true,
  };

  // A status that ends the viewer's part in the round: no bar, no action,
  // no profile line, and the registration can no longer be updated.
  const finished = (kind, next) => ({
    ...base,
    kind,
    steps: null,
    tone: BannerTone.MUTED,
    lead: null,
    next,
    showProfileLine: false,
    showRegistrationEntry: false,
  });
  const notTakingPart = () =>
    finished(BannerKind.NOT_TAKING_PART, COPY.notTakingPart(title));
  const withdrawn = () => finished(BannerKind.WITHDRAWN, COPY.withdrawn(title));

  const awaitingMatches = () => ({
    ...base,
    kind: BannerKind.AWAITING_MATCHES,
    steps: buildSteps({ isRegistered, isTrainingDone }),
    tone: BannerTone.NORMAL,
    next:
      matchAtIso && !matchDatePassed
        ? COPY.matchesAnnouncedOn(formatDay(matchAtIso, tz))
        : COPY.matchesAnnouncedSoon,
  });

  if (!isRegistered) {
    if (isRegistrationOpen) {
      return {
        ...base,
        kind: BannerKind.REGISTER,
        steps: buildSteps({ isRegistered, isTrainingDone }),
        tone: isDueSoon ? BannerTone.AMBER : BannerTone.NORMAL,
        next: !deadlineDay
          ? COPY.registerNoDate
          : isDueSoon
            ? COPY.registerBySoon(deadlineDay, inDays())
            : COPY.registerBy(deadlineDay),
        action: BannerAction.REGISTER,
      };
    }
    if (canViewMatch || matchDatePassed) {
      return noRound({ rounds, nowMs, tz });
    }
    return {
      ...base,
      kind: BannerKind.REGISTRATION_CLOSED,
      steps: buildSteps({
        registerState: StepState.FAILED,
        isRegistered,
        isTrainingDone,
      }),
      tone: BannerTone.MUTED,
      lead: null,
      next: COPY.registrationClosed(title),
      showProfileLine: false,
    };
  }

  if (canViewMatch) {
    const wasPaired = partners.length > 0;
    const isEveryPairingEnded =
      wasPaired && partners.every((partner) => partner.isActive === false);
    // A pairing that has ended keeps the registration viewable, unlike
    // leaving the round.
    const pairingEnded = (next) => ({
      ...finished(BannerKind.PAIRING_ENDED, next),
      showRegistrationEntry: true,
    });

    if (matchStatus === MatchStatus.WITHDRAWN) return withdrawn();
    if (matchStatus === MatchStatus.MATCHED) {
      if (isEveryPairingEnded) return pairingEnded(COPY.pairingEnded(title));
      return {
        ...base,
        kind: BannerKind.MATCHED,
        steps: null,
        tone: BannerTone.NORMAL,
        next: COPY.matched,
        action: BannerAction.MATCH_RESULT,
        showProfileLine: false,
      };
    }
    if (matchStatus === MatchStatus.UNMATCHED) {
      // Only a partner leaving or an admin ending the pair moves someone to
      // un_matched (leaving themselves makes them withdrawn), and it puts
      // them back in the pool, so a new match is still possible.
      if (wasPaired) return pairingEnded(COPY.pairingEndedMayRematch(title));
      return {
        ...base,
        kind: BannerKind.UNMATCHED,
        steps: null,
        tone: BannerTone.MUTED,
        lead: null,
        next: COPY.unmatched,
        showProfileLine: false,
      };
    }
    // The same rejected status covers an application turned down and
    // someone who took part and left; only the latter has a pairing.
    if (matchStatus === MatchStatus.REJECTED) {
      return wasPaired
        ? finished(
            BannerKind.PARTICIPATION_ENDED,
            COPY.participationEnded(title),
          )
        : notTakingPart();
    }
    // Still signed up (or unreadable) after the announcement: the result
    // is late, not coming soon.
    return {
      ...finished(BannerKind.RESULT_NOT_READY, COPY.resultNotReady(title)),
      showRegistrationEntry: true,
    };
  }

  if (matchDatePassed) {
    return noRound({ rounds, nowMs, tz });
  }

  // Rejected and withdrawn come from the viewer's own standing, so the
  // server reports them before the announcement too. No pairing is shown
  // yet, so a rejected viewer reads as not taking part.
  if (matchStatus === MatchStatus.REJECTED) return notTakingPart();
  if (matchStatus === MatchStatus.WITHDRAWN) return withdrawn();

  if (isTrainingDone) {
    return awaitingMatches();
  }

  const steps = buildSteps({ isRegistered, isTrainingDone });

  if (deadlineMs !== null && nowMs >= deadlineMs) {
    return {
      ...base,
      kind: BannerKind.TRAINING_OVERDUE,
      steps,
      tone: BannerTone.AMBER,
      lead: COPY.leadOverdue,
      next: COPY.trainingOverdue(
        deadlineDay,
        matchAtIso ? formatDay(matchAtIso, tz) : null,
      ),
      action: BannerAction.TRAINING,
    };
  }

  return {
    ...base,
    kind: BannerKind.TRAINING,
    steps,
    tone: isDueSoon ? BannerTone.AMBER : BannerTone.NORMAL,
    next: !deadlineDay
      ? COPY.trainingNoDate
      : isDueSoon
        ? COPY.trainingBySoon(deadlineDay, inDays())
        : COPY.trainingBy(deadlineDay),
    action: BannerAction.TRAINING,
  };
}
