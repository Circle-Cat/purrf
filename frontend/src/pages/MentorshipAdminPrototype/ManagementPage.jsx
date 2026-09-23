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

/**
 * This round's feedback: who has sent it, who still owes it, and how the
 * programme was rated.
 *
 * "Owes it" is counted over the people who actually took part and still
 * qualify — in a pair this round, not withdrawn, not blocked. Counting every
 * registration would show a list of people who were never asked.
 */
const FeedbackCard = ({ round, participants, pairs, feedback, accountOf }) => {
  const owed = participants.filter(
    (p) =>
      p.roundId === round.id &&
      p.approvalStatus !== "withdrawn" &&
      !accountOf(p.userId).isBlocked &&
      pairs.some(
        (x) =>
          x.roundId === round.id &&
          (x.mentorId === p.userId || x.menteeId === p.userId),
      ),
  );
  const sent = owed.filter((p) => feedback[p.participantId]);
  const missing = owed.filter((p) => !feedback[p.participantId]);
  const ratings = sent.map((p) => feedback[p.participantId].programRating);
  const average = ratings.length
    ? (ratings.reduce((a, b) => a + b, 0) / ratings.length).toFixed(1)
    : null;
  return (
    <Card
      title={`Feedback — ${round.name}`}
      right={
        <span className="text-xs text-slate-500">
          {sent.length} of {owed.length} sent
          {average ? ` · programme rated ${average}/5` : ""}
        </span>
      }
    >
      {owed.length === 0 ? (
        <p className="text-sm text-slate-500">
          Nobody in a pair this round yet.
        </p>
      ) : missing.length === 0 ? (
        <p className="text-sm text-slate-500">Everyone has sent theirs.</p>
      ) : (
        <p className="text-sm text-slate-700">
          <span className="text-slate-500">Not sent yet: </span>
          {missing.map((p) => p.name).join(" · ")}
        </p>
      )}
      <p className="mt-1 text-xs text-slate-500">
        Counted over people in a pair this round who have not withdrawn and are
        not blocked. What each person wrote is on their own page.
      </p>
    </Card>
  );
};

const RoundsCard = ({ rounds, roundId, onSelectRound, onEditRound, can }) => (
  <Card
    title="Rounds"
    right={
      can("mentorship.admin.write") ? (
        <Button size="sm" onClick={() => onEditRound(null)}>
          New round
        </Button>
      ) : null
    }
  >
    <ul className="divide-y divide-slate-200">
      {rounds.map((r) => (
        <li key={r.id} className="flex flex-wrap items-center gap-3 py-2">
          <button
            type="button"
            onClick={() => onSelectRound(r.id)}
            className={`text-sm font-medium ${
              r.id === roundId ? "text-slate-900" : "text-slate-500"
            }`}
          >
            {r.name}
          </button>
          <span className="text-xs text-slate-500">
            Onboarding / registration deadline {r.timeline.onboardingDeadlineAt}{" "}
            · {r.requiredMeetings} meetings required
          </span>
          {can("mentorship.admin.write") ? (
            <Button
              size="sm"
              variant="ghost"
              className="ml-auto"
              onClick={() => onEditRound(r)}
            >
              Edit
            </Button>
          ) : null}
        </li>
      ))}
    </ul>
  </Card>
);

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
  onBulkMark,
  onBulkMarkUnregistered,
  onOpenPerson,
  onEditRound,
  matchRun,
  roundClosed,
  onRunMatching,
  matchingOpen,
  unregisteredOpen,
  onOpenMatching,
  feedback,
}) => {
  // The time-limited filters belong to the round they were opened on; a
  // different round starts without them, and without the old selection.
  const onSelectRound = (id) =>
    onQueryChange({
      round: String(id),
      ...(["needs_exemption", "unregistered"].includes(query.filter)
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
            onSelectRound={onSelectRound}
            onEditRound={onEditRound}
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
              onBulkMark={onBulkMark}
              onBulkMarkUnregistered={onBulkMarkUnregistered}
              onOpenPerson={onOpenPerson}
              matchRun={matchRun}
              roundClosed={roundClosed}
              matchingOpen={matchingOpen}
              unregisteredOpen={unregisteredOpen}
              onRunMatching={onRunMatching}
            />
          </Card>

          {can("mentorship.feedback.read") ? (
            <FeedbackCard
              round={round}
              participants={participants}
              pairs={pairs}
              feedback={feedback}
              accountOf={accountOf}
            />
          ) : null}
        </>
      ) : null}
    </>
  );
};

export default ManagementPage;
