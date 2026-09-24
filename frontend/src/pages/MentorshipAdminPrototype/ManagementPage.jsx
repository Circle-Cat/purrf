import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import ParticipantsTable from "@/pages/MentorshipAdminPrototype/ParticipantsTable";
import {
  feedbackOwedBy,
  roundFigures,
} from "@/pages/MentorshipAdminPrototype/feedback";
import {
  ACTION_LABELS,
  ACTOR_NAMES,
} from "@/pages/MentorshipAdminPrototype/mockData";

const Card = ({ title, right, children }) => (
  <section className="mb-6 rounded-lg border border-slate-200 bg-white">
    <header className="flex items-center gap-3 border-b border-slate-200 px-5 py-3">
      <h2 className="text-sm font-semibold">{title}</h2>
      <div className="ml-auto flex items-center gap-2">{right}</div>
    </header>
    <div className="px-5 py-4">{children}</div>
  </section>
);

/**
 * The pending-approval card.
 *
 * It sits above everything else because it is the only thing on this page that
 * is waiting on the reader, and it renders for nobody without the approve
 * permission — not greyed out, absent. It holds pending requests only: a
 * decided one is already visible as a note on the person's timeline, which is
 * where you would go looking for it afterwards anyway.
 *
 * The decision note is optional and travels with the decision into the note
 * the approval writes, so "approved, but talk to her first" is not lost.
 *
 * Every request names a reviewer, and the ones sent to you come first — but
 * any approver may decide any of them. The one exception is a request you
 * raised yourself: it is listed, and left for someone else.
 *
 * A request that could not be applied because things changed since it was
 * raised is not dropped in silence: it stays on the card under "Not applied",
 * with the reason, so whoever pressed Approve sees that nothing happened.
 */
const ApprovalsCard = ({ requests, viewerId, onDecide }) => {
  const pending = requests
    .filter((r) => r.status === "pending")
    .sort(
      (a, b) =>
        Number(b.reviewerId === viewerId) - Number(a.reviewerId === viewerId),
    );
  const mine = pending.filter((r) => r.reviewerId === viewerId).length;
  const invalidated = requests.filter((r) => r.status === "invalidated");
  const [decisionNotes, setDecisionNotes] = useState({});
  const decide = (requestId, approved) =>
    onDecide(requestId, approved, decisionNotes[requestId]?.trim() || null);
  return (
    <Card
      title="Pending approvals"
      right={
        <span className="text-xs text-slate-500">
          {pending.length} waiting · {mine} sent to you
        </span>
      }
    >
      {pending.length === 0 ? (
        <p className="text-sm text-slate-500">Nothing waiting.</p>
      ) : (
        <ul className="divide-y divide-slate-200">
          {pending.map((r) => (
            <li key={r.requestId} className="flex flex-wrap gap-3 py-3">
              <div className="min-w-64 flex-1">
                <p className="text-sm font-medium">
                  {ACTION_LABELS[r.action]} — {r.targetLabel}
                </p>
                <p className="mt-1 text-sm text-slate-600">{r.reason}</p>
                <p className="mt-1 text-xs text-slate-500">
                  Raised by {ACTOR_NAMES[r.raisedBy]} · {r.createdAt} · Sent to{" "}
                  {r.reviewerId === viewerId ? (
                    <strong>you</strong>
                  ) : (
                    ACTOR_NAMES[r.reviewerId]
                  )}
                </p>
              </div>
              {r.raisedBy === viewerId ? (
                <p className="self-center text-xs text-slate-500">
                  You raised this — another approver decides it.
                </p>
              ) : (
                <div className="flex flex-wrap items-start gap-2">
                  <Input
                    aria-label={`Decision note for request ${r.requestId}`}
                    value={decisionNotes[r.requestId] ?? ""}
                    onChange={(e) =>
                      setDecisionNotes((all) => ({
                        ...all,
                        [r.requestId]: e.target.value,
                      }))
                    }
                    placeholder="Decision note (optional)"
                    className="h-8 w-56 text-sm"
                  />
                  <Button size="sm" onClick={() => decide(r.requestId, true)}>
                    Approve
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => decide(r.requestId, false)}
                  >
                    Reject
                  </Button>
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
      {invalidated.length > 0 ? (
        <div className="mt-3 border-t border-slate-200 pt-3">
          <p className="text-xs font-medium uppercase tracking-wide text-slate-400">
            Not applied — things changed since it was raised
          </p>
          <ul className="mt-1 divide-y divide-slate-100">
            {invalidated.map((r) => (
              <li
                key={r.requestId}
                aria-label={`Not applied: ${ACTION_LABELS[r.action]} — ${r.targetLabel}`}
                className="py-2 text-sm"
              >
                <span className="font-medium">
                  {ACTION_LABELS[r.action]} — {r.targetLabel}
                </span>
                <span className="block text-xs text-amber-900">
                  {r.invalidReason} Checked by {ACTOR_NAMES[r.decidedBy]} on{" "}
                  {r.decidedAt}; nothing was changed.
                </span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </Card>
  );
};

const formatRating = (value) => (value != null ? value.toFixed(2) : "—");

/**
 * The rounds table, in the shape main's "Mentorship Round Management" card
 * already has — same columns, same footer — plus a Feedback column for
 * whoever may read feedback. The round name also picks the round the rest of
 * the page is about.
 *
 * @param {object} props
 * @param {Array<object>} props.rounds
 * @param {number} props.roundId - The round the page is on.
 * @param {Array<object>} props.participants - Every round's rows.
 * @param {Array<object>} props.pairs - Every round's pairs.
 * @param {Object<string, object>} props.feedback - Keyed by participant id.
 * @param {Function} props.accountOf
 * @param {Function} props.onSelectRound
 * @param {Function} props.onEditRound
 * @param {Function} props.onOpenFeedback
 * @param {Function} props.can
 * @returns {JSX.Element}
 */
const RoundsCard = ({
  rounds,
  roundId,
  participants,
  pairs,
  feedback,
  accountOf,
  onSelectRound,
  onEditRound,
  onOpenFeedback,
  can,
}) => {
  const writable = can("mentorship.admin.write");
  const feedbackReadable = can("mentorship.feedback.read");
  const rows = rounds.map((r) => {
    const owed = feedbackOwedBy(r, participants, pairs, accountOf);
    return {
      round: r,
      figures: roundFigures(r, participants, pairs, feedback),
      owed: owed.length,
      sent: owed.filter((p) => feedback[p.participantId]).length,
    };
  });
  const totals = {
    completedRounds: rounds.filter((r) => r.status === "closed").length,
    participants: rows.reduce((s, r) => s + r.figures.matchedParticipants, 0),
    meetings: rows.reduce((s, r) => s + r.figures.completedMeetings, 0),
  };
  const th = "px-3 py-2 text-left text-xs font-medium text-slate-500";
  const td = "px-3 py-2 text-sm";
  return (
    <Card
      title="Mentorship Round Management"
      right={
        writable ? (
          <Button size="sm" onClick={() => onEditRound(null)}>
            Create New Round
          </Button>
        ) : null
      }
    >
      <table className="w-full">
        <thead className="border-b border-slate-200">
          <tr>
            <th className={th}>Round Name</th>
            <th className={th}>Participants</th>
            <th className={th}>Required Meetings</th>
            <th className={th}>Mentor Rating</th>
            <th className={th}>Mentee Rating</th>
            <th className={th}>Average Meetings Per Pair</th>
            {feedbackReadable ? <th className={th}>Feedback</th> : null}
            <th className={th}>Action</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {rows.map(({ round: r, figures, owed, sent }) => (
            <tr key={r.id} className={r.id === roundId ? "bg-slate-50" : ""}>
              <td className={td}>
                <button
                  type="button"
                  aria-pressed={r.id === roundId}
                  onClick={() => onSelectRound(r.id)}
                  className={`text-left font-medium ${
                    r.id === roundId ? "text-slate-900" : "text-slate-500"
                  }`}
                >
                  {r.name}
                </button>
              </td>
              <td className={td}>{figures.matchedParticipants}</td>
              <td className={td}>{r.requiredMeetings} times</td>
              <td className={td}>{formatRating(figures.mentorRating)}</td>
              <td className={td}>{formatRating(figures.menteeRating)}</td>
              <td className={td}>
                {figures.avgMeetingsPerPair != null
                  ? figures.avgMeetingsPerPair.toFixed(1)
                  : "—"}
              </td>
              {feedbackReadable ? (
                <td className={td}>
                  <button
                    type="button"
                    className="underline underline-offset-2"
                    aria-label={`Feedback for ${r.name}`}
                    onClick={() => onOpenFeedback(r.id)}
                  >
                    {sent} of {owed} sent
                  </button>
                </td>
              ) : null}
              <td className={td}>
                <Button
                  size="sm"
                  variant="ghost"
                  aria-label={writable ? `Edit ${r.name}` : `View ${r.name}`}
                  onClick={() => onEditRound(r)}
                >
                  {writable ? "Edit" : "View"}
                </Button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="mt-2 flex flex-wrap gap-6 border-t border-slate-200 bg-slate-50 px-3 py-2 text-sm font-semibold text-slate-700">
        <span>Total Completed Rounds: {totals.completedRounds}</span>
        <span>Total Participants: {totals.participants}</span>
        <span>Total Meetings: {totals.meetings}</span>
      </div>
    </Card>
  );
};

/**
 * ManagementPage
 *
 * The console home: approvals, rounds, and the one participant table.
 * Everything deeper than a list lives on its own route.
 *
 * @returns {JSX.Element}
 */
const ManagementPage = ({
  round,
  rounds,
  query,
  onQueryChange,
  participants,
  nonParticipants,
  emails,
  notes,
  notifications,
  pairs,
  requests,
  viewerId,
  flagsByParticipant,
  exemptParticipantIds,
  accountOf,
  can,
  onDecide,
  onOpenParticipant,
  onMarkCell,
  onCompose,
  onOpenPerson,
  onEditRound,
  matchRun,
  onRunMatching,
  matchingOpen,
  roundRunning,
  onOpenMatching,
  feedback,
  onOpenFeedback,
}) => {
  // The time-limited filters belong to the round they were opened on; a
  // different round starts without them, and without the old selection.
  const onSelectRound = (id) =>
    onQueryChange({
      round: String(id),
      ...(["eligible", "needs_exemption", "unregistered"].includes(query.filter)
        ? { filter: "" }
        : {}),
    });

  return (
    <>
      {can("mentorship.approve") ? (
        <ApprovalsCard
          requests={requests}
          viewerId={viewerId}
          onDecide={onDecide}
        />
      ) : null}

      {can("mentorship.admin.read") || can("mentorship.admin.write") ? (
        <>
          <RoundsCard
            rounds={rounds}
            roundId={round.id}
            participants={participants}
            pairs={pairs}
            feedback={feedback}
            accountOf={accountOf}
            onSelectRound={onSelectRound}
            onEditRound={onEditRound}
            onOpenFeedback={onOpenFeedback}
            can={can}
          />

          <Card
            title="Participants"
            right={
              <>
                <Button
                  size="sm"
                  variant="outline"
                  disabled={!matchRun}
                  onClick={onOpenMatching}
                  title={
                    matchRun ? undefined : "No matching run for this round yet"
                  }
                >
                  {matchRun?.status === "running"
                    ? "Matching running…"
                    : "View matching results"}
                </Button>
                <Select
                  value={String(round.id)}
                  onValueChange={(v) => onSelectRound(Number(v))}
                >
                  <SelectTrigger className="h-8 w-56 text-xs">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {rounds.map((r) => (
                      <SelectItem key={r.id} value={String(r.id)}>
                        {r.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </>
            }
          >
            <ParticipantsTable
              key={round.id}
              query={query}
              onQueryChange={onQueryChange}
              round={round}
              participants={participants.filter((p) => p.roundId === round.id)}
              nonParticipants={nonParticipants}
              pairs={pairs.filter((p) => p.roundId === round.id)}
              flagsByParticipant={flagsByParticipant}
              exemptParticipantIds={exemptParticipantIds}
              accountOf={accountOf}
              emails={emails}
              notes={notes}
              notifications={notifications}
              can={can}
              onOpenParticipant={onOpenParticipant}
              onMarkCell={onMarkCell}
              onCompose={onCompose}
              onOpenPerson={onOpenPerson}
              matchRun={matchRun}
              matchingOpen={matchingOpen}
              roundRunning={roundRunning}
              onRunMatching={onRunMatching}
            />
          </Card>
        </>
      ) : null}
    </>
  );
};

export default ManagementPage;
