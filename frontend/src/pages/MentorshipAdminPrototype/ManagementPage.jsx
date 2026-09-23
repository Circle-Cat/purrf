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
 */
const ApprovalsCard = ({ requests, viewerId, onDecide }) => {
  const pending = requests
    .filter((r) => r.status === "pending")
    .sort(
      (a, b) =>
        Number(b.reviewerId === viewerId) - Number(a.reviewerId === viewerId),
    );
  const mine = pending.filter((r) => r.reviewerId === viewerId).length;
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
 * The console home: approvals, rounds, and the participant search that carries
 * three tabs. Everything deeper than a list lives on its own route.
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
  pairs,
  requests,
  viewerId,
  flagsByParticipant,
  can,
  onDecide,
  onOpenParticipant,
  onOpenPair,
  onMarkCell,
  onCompose,
  onBulkMark,
  onConfirmUnmatched,
  onEditRound,
}) => {
  const onSelectRound = (id) => onQueryChange({ round: String(id) });

  return (
    <>
      {can("mentorship.approve") ? (
        <ApprovalsCard
          requests={requests}
          viewerId={viewerId}
          onDecide={onDecide}
        />
      ) : null}

      {can("mentorship.admin.read") ? (
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
            }
          >
            <ParticipantsTable
              query={query}
              onQueryChange={onQueryChange}
              round={round}
              participants={participants.filter((p) => p.roundId === round.id)}
              nonParticipants={nonParticipants.filter(
                (p) => p.roundId === round.id,
              )}
              pairs={pairs.filter((p) => p.roundId === round.id)}
              flagsByParticipant={flagsByParticipant}
              can={can}
              onOpenParticipant={onOpenParticipant}
              onOpenPair={onOpenPair}
              onMarkCell={onMarkCell}
              onCompose={onCompose}
              onBulkMark={onBulkMark}
              onConfirmUnmatched={onConfirmUnmatched}
            />
          </Card>
        </>
      ) : null}
    </>
  );
};

export default ManagementPage;
