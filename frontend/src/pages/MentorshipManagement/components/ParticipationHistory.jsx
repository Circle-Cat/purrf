import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { MentorshipParticipantRoleLabels } from "@/constants/MentorshipParticipantRoles";
import { userDisplayName } from "@/utils/userName";
import { useParticipantDetail } from "@/pages/MentorshipManagement/hooks/useParticipantDetail";
import MarkBadges from "@/pages/MentorshipManagement/components/MarkBadges";
import PairSection from "@/pages/MentorshipManagement/components/PairSection";
import NoteTimeline from "@/pages/MentorshipManagement/components/NoteTimeline";
import ParticipantFeedback from "@/pages/MentorshipManagement/components/ParticipantFeedback";

const NOOP = () => {};

/**
 * One earlier round, opened in place: that round's pairs and meeting logs,
 * timeline and feedback, all read-only. Loaded only once opened.
 *
 * @param {{userId: number, subjectName: string, roundId: number}} props
 */
const HistoryRoundBody = ({ userId, subjectName, roundId }) => {
  const { detail, loading, error } = useParticipantDetail(roundId, userId);
  const [openPairId, setOpenPairId] = useState(null);
  if (loading) {
    return <p className="py-2 text-sm text-muted-foreground">Loading…</p>;
  }
  if (error || !detail) {
    return (
      <p className="py-2 text-sm text-destructive">
        Couldn&apos;t load this round.
      </p>
    );
  }
  const registration = detail.registration;
  const subject = {
    userId,
    name: subjectName,
    role: registration?.participantRole,
  };
  return (
    <div className="space-y-4 py-2">
      {(registration?.pairs ?? []).map((pair) => (
        <PairSection
          key={pair.pairId}
          pair={pair}
          subject={subject}
          round={detail.round}
          canWrite={false}
          open={openPairId === pair.pairId}
          onToggle={() =>
            setOpenPairId((id) => (id === pair.pairId ? null : pair.pairId))
          }
          onMeetingsSaved={NOOP}
        />
      ))}
      <NoteTimeline
        notes={detail.notes}
        roundId={roundId}
        userId={userId}
        canAdd={false}
        onAdded={NOOP}
        pairs={registration?.pairs ?? []}
      />
      <ParticipantFeedback feedback={detail.feedback} />
    </div>
  );
};

/**
 * The rounds this person took part in that ended before the page's round,
 * newest first, one row each. A row opens in place, read-only.
 *
 * @param {{userId: number, subjectName: string, history: Object[]}} props
 */
const ParticipationHistory = ({ userId, subjectName, history }) => {
  const [openRoundId, setOpenRoundId] = useState(null);
  return (
    <section>
      <h3 className="mb-2 text-sm font-semibold">Participation history</h3>
      {history.length === 0 ? (
        <p className="text-sm text-muted-foreground">No earlier rounds.</p>
      ) : (
        <ul className="divide-y rounded-md border border-slate-200">
          {history.map((row) => {
            const open = openRoundId === row.roundId;
            return (
              <li key={row.roundId} className="px-4 py-2">
                <button
                  type="button"
                  aria-expanded={open}
                  onClick={() => setOpenRoundId(open ? null : row.roundId)}
                  className="flex w-full flex-wrap items-center gap-2 text-left text-sm"
                >
                  <span className="text-slate-500">{open ? "▾" : "▸"}</span>
                  <span className="font-medium">{row.roundName}</span>
                  <span className="text-slate-500">
                    {MentorshipParticipantRoleLabels[row.participantRole] ??
                      row.participantRole}
                  </span>
                  {row.approvalStatus && (
                    <Badge variant="secondary">{row.approvalStatus}</Badge>
                  )}
                  {row.exempted && (
                    <Badge
                      variant="outline"
                      className="border-green-300 bg-green-50 text-green-800"
                    >
                      Exempted
                    </Badge>
                  )}
                  <MarkBadges
                    noShow={row.marks?.noShow}
                    redFlag={row.marks?.redFlag}
                  />
                  {row.pairs.map((pair) => (
                    <span key={pair.pairId} className="text-xs text-slate-500">
                      {`${userDisplayName(pair.partner)} · ${pair.completedMeetingCount}/${row.requiredMeetings ?? "—"}`}
                    </span>
                  ))}
                </button>
                {open && (
                  <HistoryRoundBody
                    userId={userId}
                    subjectName={subjectName}
                    roundId={row.roundId}
                  />
                )}
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
};

export default ParticipationHistory;
