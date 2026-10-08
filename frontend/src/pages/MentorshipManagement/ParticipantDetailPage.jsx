import { useEffect, useRef, useState } from "react";
import {
  Link,
  useLocation,
  useNavigate,
  useParams,
  useSearchParams,
} from "react-router-dom";
import { ArrowLeft } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { ROUTE_PATHS } from "@/constants/RoutePaths";
import { PERMISSIONS } from "@/constants/Permissions";
import { FEATURE_FLAGS } from "@/constants/FeatureFlags";
import { MentorshipParticipantRoles } from "@/constants/MentorshipParticipantRoles";
import { useAuth } from "@/context/auth";
import { useFeatureFlags } from "@/hooks/useFeatureFlags";
import { userDisplayName } from "@/utils/userName";
import {
  getAllMentorshipRounds,
  searchParticipants,
} from "@/api/mentorshipApi";
import StateChips from "@/pages/AdminAccounts/components/StateChips";
import ExemptionCell from "@/pages/MentorshipManagement/components/ExemptionCell";
import { exemptionWhyLines } from "@/pages/MentorshipManagement/utils/approvalLabels";
import { useParticipantDetail } from "@/pages/MentorshipManagement/hooks/useParticipantDetail";
import PairSection from "@/pages/MentorshipManagement/components/PairSection";
import NoteTimeline from "@/pages/MentorshipManagement/components/NoteTimeline";
import ParticipantFeedback from "@/pages/MentorshipManagement/components/ParticipantFeedback";
import ParticipationHistory from "@/pages/MentorshipManagement/components/ParticipationHistory";
import BlockFromPurrf from "@/pages/MentorshipManagement/components/BlockFromPurrf";

const ROLE_LABELS = {
  [MentorshipParticipantRoles.MENTOR]: "Mentor",
  [MentorshipParticipantRoles.MENTEE]: "Mentee",
};

/**
 * The round to open when the URL names none: the latest round this person
 * registered for, else the latest round. The rounds API lists latest first.
 *
 * @param {string} userId
 * @param {boolean} needed
 * @returns {{roundId: string|null, failed: boolean}}
 */
const useFallbackRoundId = (userId, needed) => {
  const [roundId, setRoundId] = useState(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    if (!needed) return undefined;
    let cancelled = false;
    Promise.all([
      getAllMentorshipRounds(),
      searchParticipants({ userId: Number(userId) }),
    ])
      .then(([rounds, rows]) => {
        if (cancelled) return;
        const list = rounds.data ?? [];
        const registered = new Set(
          (rows.data?.participantRows ?? []).map((row) => row.roundId),
        );
        const pick = list.find((r) => registered.has(r.id)) ?? list[0];
        if (pick) setRoundId(String(pick.id));
        else setFailed(true);
      })
      .catch(() => {
        if (!cancelled) setFailed(true);
      });
    return () => {
      cancelled = true;
    };
  }, [userId, needed]);

  return { roundId, failed };
};

/**
 * Why this person is kept out of matching by their history, and the
 * exemption control (behind the matching-run flag, like the list's). Once
 * exempted, says so instead.
 */
const ExemptionBox = ({
  registration,
  exempted,
  roundId,
  matchingOn,
  canWrite,
  canApprove,
  userId,
  onChanged,
}) => {
  if (exempted) {
    return (
      <div className="rounded-md border border-green-200 bg-green-50 px-3 py-2 text-sm text-green-800">
        Exempted
      </div>
    );
  }
  const lines = exemptionWhyLines(registration.exemptionFindings);
  if (lines.length === 0) return null;
  return (
    <div className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900">
      <ul className="space-y-0.5">
        {lines.map((line) => (
          <li key={line}>{line}</li>
        ))}
      </ul>
      {matchingOn && (
        <div className="mt-2">
          <ExemptionCell
            row={registration}
            roundId={roundId}
            canWrite={canWrite}
            canApprove={canApprove}
            userId={userId}
            onChanged={onChanged}
          />
        </div>
      )}
    </div>
  );
};

/**
 * ParticipantDetailPage
 *
 * One person in one round: who they are, their status and pairs with each
 * pair's meeting log, the round's notes, their feedback, and the rounds they
 * took part in before. Registered or not, the same page. Writing (notes,
 * meeting edits, exemptions) needs mentorship write access and a round in
 * progress; asking for a block needs write access only.
 *
 * Route: /mentorship-management/participants/:userId?round=&pair=
 */
const ParticipantDetailPage = () => {
  const { userId } = useParams();
  const [searchParams] = useSearchParams();
  const roundId = searchParams.get("round");
  const pairParam = searchParams.get("pair");
  const location = useLocation();
  const navigate = useNavigate();
  const returnSearch = location.state?.returnSearch;

  const fallback = useFallbackRoundId(userId, !roundId);
  useEffect(() => {
    if (roundId || !fallback.roundId) return;
    navigate(
      { search: `?round=${fallback.roundId}` },
      { replace: true, state: location.state },
    );
  }, [roundId, fallback.roundId, navigate, location.state]);

  const { detail, loading, error, refetch } = useParticipantDetail(
    roundId,
    userId,
  );
  const { permissions, user } = useAuth();
  const canWrite = permissions.includes(PERMISSIONS.MENTORSHIP_ADMIN_WRITE);
  const canApprove = permissions.includes(PERMISSIONS.MENTORSHIP_APPROVE);
  const matchingOn = Boolean(useFeatureFlags()[FEATURE_FLAGS.MATCHING_RUN]);

  // Which pair's meeting log is open. The URL's pair wins; with no pair in
  // the URL, a single pair opens by itself. Applied once per person, round
  // and URL pair, when that detail first arrives, so a quiet refetch after a
  // note or a save leaves the open pair and the scroll position alone.
  const [openPairId, setOpenPairId] = useState(null);
  const appliedFor = useRef(null);
  const pairs = detail?.registration?.pairs ?? [];
  useEffect(() => {
    if (
      !detail ||
      String(detail.round?.roundId) !== String(roundId) ||
      String(detail.person?.userId) !== String(userId)
    ) {
      return;
    }
    const key = `${userId}|${roundId}|${pairParam ?? ""}`;
    if (appliedFor.current === key) return;
    appliedFor.current = key;
    const loaded = detail.registration?.pairs ?? [];
    if (pairParam != null) {
      setOpenPairId(Number(pairParam));
      document
        .getElementById(`pair-${pairParam}`)
        ?.scrollIntoView?.({ block: "start" });
    } else {
      setOpenPairId(loaded.length === 1 ? loaded[0].pairId : null);
    }
  }, [userId, roundId, pairParam, detail]);

  const back = (
    <Link
      to={{
        pathname: ROUTE_PATHS.MENTORSHIP_MANAGEMENT,
        search: typeof returnSearch === "string" ? returnSearch : "",
      }}
      className="flex w-fit items-center gap-1 text-sm text-gray-600 hover:text-gray-900"
    >
      <ArrowLeft className="h-4 w-4" />
      Participants
    </Link>
  );

  let body;
  if (fallback.failed) {
    body = (
      <p className="py-10 text-center text-gray-500">
        No mentorship rounds yet.
      </p>
    );
  } else if (!roundId || loading) {
    body = (
      <p className="py-10 text-center text-gray-500">Loading participant...</p>
    );
  } else if (error || !detail) {
    body = (
      <p className="py-10 text-center text-gray-500">
        Could not load this participant.
      </p>
    );
  } else {
    const { person, round, registration } = detail;
    const name = userDisplayName(person);
    const writable = canWrite && round.inProgress;
    const role = registration?.participantRole;
    const trainingStatus =
      role === MentorshipParticipantRoles.MENTEE
        ? registration?.menteeOnboardingStatus
        : registration?.mentorOnboardingStatus;
    const subject = { userId: person.userId, name, role };
    const idLine = [
      `ID ${person.userId}`,
      ROLE_LABELS[role] ?? "Not registered",
      person.isInternal ? "Internal" : "External",
      person.primaryEmail,
    ]
      .filter(Boolean)
      .join(" · ");
    const orderedPairs = [...pairs].sort(
      (a, b) =>
        Number(a.partner.isActive === false) -
          Number(b.partner.isActive === false) || a.pairId - b.pairId,
    );

    body = (
      <div className="space-y-6">
        <div className="flex flex-wrap items-start gap-4">
          <div>
            <h2 className="text-lg font-semibold">{name}</h2>
            <p className="text-sm text-muted-foreground">{idLine}</p>
            <div className="mt-1">
              <StateChips
                isActive={!person.isDeactivated}
                isBlocked={person.isBlocked}
                hasPendingBlockRequest={false}
              />
            </div>
          </div>
          <div className="ml-auto">
            <BlockFromPurrf
              person={person}
              pendingBlockRequest={detail.pendingBlockRequest}
              canWrite={canWrite}
              onRequested={refetch}
            />
          </div>
        </div>

        {!round.inProgress && (
          <p className="rounded-md bg-slate-100 px-3 py-2 text-sm text-slate-700">
            This round has ended. The page is read-only.
          </p>
        )}

        <section aria-label={round.name} className="space-y-3">
          <h3 className="text-sm font-semibold">{round.name}</h3>
          {!registration ? (
            <p className="text-sm text-muted-foreground">
              Not registered for this round.
            </p>
          ) : (
            <>
              <div className="flex flex-wrap items-center gap-3 text-sm">
                {registration.approvalStatus && (
                  <Badge variant="secondary">
                    {registration.approvalStatus}
                  </Badge>
                )}
                <span className="text-slate-600">
                  {trainingStatus == null
                    ? "No course"
                    : trainingStatus === "done"
                      ? "Training done"
                      : "Training not done"}
                </span>
                {pairs.length === 0 && (
                  <span className="text-slate-600">No pair this round</span>
                )}
              </div>
              {round.inProgress && (
                <ExemptionBox
                  registration={registration}
                  exempted={detail.exempted}
                  roundId={round.roundId}
                  matchingOn={matchingOn}
                  canWrite={canWrite}
                  canApprove={canApprove}
                  userId={user?.userId}
                  onChanged={refetch}
                />
              )}
              {orderedPairs.map((pair) => (
                <PairSection
                  key={pair.pairId}
                  pair={pair}
                  subject={subject}
                  round={round}
                  canWrite={writable}
                  open={openPairId === pair.pairId}
                  onToggle={() =>
                    setOpenPairId((id) =>
                      id === pair.pairId ? null : pair.pairId,
                    )
                  }
                  onMeetingsSaved={refetch}
                />
              ))}
            </>
          )}
        </section>

        <NoteTimeline
          notes={detail.notes}
          roundId={round.roundId}
          userId={person.userId}
          canAdd={writable}
          onAdded={refetch}
        />

        <ParticipantFeedback feedback={detail.feedback} />

        <ParticipationHistory
          userId={person.userId}
          subjectName={name}
          history={detail.history}
        />
      </div>
    );
  }

  return (
    <Card className="border-gray-200">
      <CardHeader className="space-y-2">{back}</CardHeader>
      <CardContent>{body}</CardContent>
    </Card>
  );
};

export default ParticipantDetailPage;
