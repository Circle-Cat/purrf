import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import FlagBadges from "@/pages/MentorshipAdminPrototype/FlagBadges";
import {
  ACTION_LABELS,
  ACTOR_NAMES,
  NOTE_KIND,
  NOTE_LABELS,
  TEMPLATE_LABELS,
} from "@/pages/MentorshipAdminPrototype/mockData";

const TIMELINE_FILTERS = [
  { key: "all", label: "All" },
  { key: "note", label: "Notes only" },
  { key: "email", label: "Emails only" },
];

const Block = ({ title, right, children }) => (
  <section className="border-t border-slate-200 px-5 py-4">
    <header className="mb-3 flex items-center gap-3">
      <h3 className="text-sm font-semibold">{title}</h3>
      <div className="ml-auto">{right}</div>
    </header>
    {children}
  </section>
);

/**
 * One line of the note timeline.
 *
 * The three kinds are marked differently on purpose. A "decided" note is not
 * something anyone typed into this page — it exists because a request was
 * approved, and saying so stops the next reader assuming the admin could have
 * written it directly.
 *
 * A decided flag can be revoked, which is itself a judgement and so goes for
 * approval too. A revoked flag stays, struck through: what was once decided
 * about someone is part of their record even after it is taken back.
 */
const NoteRow = ({ note, revoked, onRevoke }) => {
  const kind = note.tag ? NOTE_KIND[note.tag] : "written";
  return (
    <li className="flex gap-3 py-2">
      <span className="w-40 shrink-0 text-xs">
        {note.tag ? (
          <Badge variant={kind === "decided" ? "destructive" : "secondary"}>
            {NOTE_LABELS[note.tag]}
          </Badge>
        ) : (
          <span className="text-slate-400">Note</span>
        )}
      </span>
      <span className="w-40 shrink-0 text-xs text-slate-500">
        {ACTOR_NAMES[note.authorId]} · {note.createdAt}
      </span>
      <span className="flex-1 text-sm text-slate-700">
        <span className={revoked ? "line-through" : ""}>
          {note.body || <em className="text-slate-400">No comment</em>}
        </span>
        {kind === "decided" ? (
          <em className="ml-2 text-xs text-slate-500">
            {revoked ? "(revoked)" : "(via approval)"}
          </em>
        ) : null}
      </span>
      {kind === "decided" && !revoked && onRevoke ? (
        <Button size="sm" variant="ghost" onClick={() => onRevoke(note)}>
          Revoke
        </Button>
      ) : null}
    </li>
  );
};

/**
 * One email on the timeline — a message Purrf sent, or a reply pulled back in.
 *
 * The template name leads because it answers the question people come here
 * with ("did she get the mid-term reminder?"); the body is only a glimpse.
 */
const EmailRow = ({ email, personName }) => (
  <li className="flex gap-3 py-2">
    <span className="w-40 shrink-0 text-xs">
      <Badge variant="outline">
        {email.direction === "out" ? "Email sent" : "Reply"}
      </Badge>
    </span>
    <span className="w-40 shrink-0 text-xs text-slate-500">
      {email.direction === "out"
        ? ACTOR_NAMES[email.sentBy]
        : `From ${personName}`}{" "}
      · {email.at}
    </span>
    <span className="flex-1 text-sm text-slate-700">
      <span className="font-medium">
        {email.direction === "in" ? "Re: " : ""}
        {TEMPLATE_LABELS[email.templateKey]}
      </span>
      <span className="ml-2 text-slate-500">{email.body}</span>
    </span>
  </li>
);

/**
 * ParticipantDetailPage
 *
 * Everything that belongs to a *person*: how this round is going for them,
 * their timeline, every round they have taken part in, and the feedback they
 * wrote.
 *
 * The timeline is notes and emails together, newest first. "What has happened
 * with her" is one question; answering it from two lists means interleaving
 * them by date in your head.
 *
 * Meetings are deliberately not here. A mentor carrying two mentees has two
 * meeting logs, and flattening them onto one page would invent a number that
 * does not exist. The count links to the pair instead.
 *
 * @returns {JSX.Element}
 */
const ParticipantDetailPage = ({
  person,
  rounds,
  participants,
  pairs,
  notes,
  emails,
  onRefreshEmails,
  feedback,
  can,
  backLabel,
  onBack,
  onOpenPair,
  onAddNote,
  onRaise,
  onCompose,
  flags,
  revokedNoteIds,
  requests,
  viewerId,
  onCancelRequest,
  onRevoke,
}) => {
  const [filter, setFilter] = useState("all");
  const [syncMessage, setSyncMessage] = useState(null);
  if (!person) return null;

  const round = rounds.find((r) => r.id === person.roundId);
  const myPairs = pairs.filter(
    (p) =>
      p.roundId === person.roundId &&
      (p.mentorId === person.userId || p.menteeId === person.userId),
  );
  const history = participants
    .filter((p) => p.userId === person.userId)
    .map((p) => ({
      participant: p,
      round: rounds.find((r) => r.id === p.roundId),
      pair: pairs.find(
        (x) =>
          x.roundId === p.roundId &&
          (x.mentorId === p.userId || x.menteeId === p.userId),
      ),
    }))
    .sort((a, b) =>
      (b.round?.timeline.meetingsCompletionDeadlineAt ?? "").localeCompare(
        a.round?.timeline.meetingsCompletionDeadlineAt ?? "",
      ),
    );

  const registered = person.participantId != null;

  const timeline = [
    ...notes
      .filter((n) => n.userId === person.userId && n.roundId === person.roundId)
      .map((n) => ({ kind: "note", at: n.createdAt, item: n })),
    ...emails.map((e) => ({ kind: "email", at: e.at, item: e })),
  ]
    .filter((entry) => filter === "all" || entry.kind === filter)
    .sort((a, b) => b.at.localeCompare(a.at));

  const refresh = () => {
    const count = onRefreshEmails();
    setSyncMessage(
      count === 0
        ? "Checked the mailbox — no new replies."
        : `Checked the mailbox — ${count} new ${count === 1 ? "reply" : "replies"}.`,
    );
  };
  const writable = can("mentorship.admin.write");

  return (
    <div className="rounded-lg border border-slate-200 bg-white">
      <header className="flex flex-wrap items-center gap-3 px-5 py-4">
        <Button size="sm" variant="ghost" onClick={onBack}>
          {backLabel}
        </Button>
        <div>
          <h2 className="text-base font-semibold">{person.name}</h2>
          <p className="text-xs text-slate-500">
            {[person.role, person.identity, person.email]
              .filter(Boolean)
              .join(" · ")}
          </p>
        </div>
      </header>

      <Block
        title={round?.name ?? "This round"}
        right={
          writable ? (
            <div className="flex gap-2">
              <Button size="sm" variant="outline" onClick={onCompose}>
                Send email
              </Button>
              {registered ? (
                <Button size="sm" onClick={onRaise}>
                  Change status / flag
                </Button>
              ) : null}
            </div>
          ) : null
        }
      >
        {registered ? null : (
          <p className="text-sm text-slate-600">
            Not registered for this round. Notes and emails here are kept
            against {person.name} and {round?.name}, and stay on this timeline
            if they register.
          </p>
        )}
        <div
          className={`flex flex-wrap items-center gap-4 text-sm ${
            registered ? "" : "hidden"
          }`}
        >
          <span>
            <Badge variant="secondary">{person.approvalStatus}</Badge>
            <FlagBadges flags={flags} />
          </span>
          <span>Onboarding {person.onboardingDone ? "done" : "not done"}</span>
          {myPairs.length === 0 ? (
            <span className="text-slate-500">No pair this round</span>
          ) : myPairs.length === 1 ? (
            <button
              type="button"
              className="underline-offset-2 hover:underline"
              onClick={() => onOpenPair(myPairs[0].pairId)}
            >
              With{" "}
              {myPairs[0].mentorId === person.userId
                ? myPairs[0].menteeName
                : myPairs[0].mentorName}{" "}
              · {myPairs[0].completed}/{myPairs[0].required} meetings ↗
            </button>
          ) : (
            <span>
              {myPairs.length} mentees —{" "}
              <button
                type="button"
                className="underline-offset-2 hover:underline"
                onClick={() => onOpenPair(myPairs[0].pairId)}
              >
                see the Pairs tab ↗
              </button>
            </span>
          )}
        </div>
        {myPairs.length > 1 ? (
          <p className="mt-2 text-xs text-slate-500">
            Meetings are counted per pair, so there is no single number for a
            mentor carrying more than one mentee.
          </p>
        ) : null}
      </Block>

      {requests.length > 0 ? (
        <Block title="Waiting on a decision">
          <ul className="divide-y divide-slate-100 text-sm">
            {requests.map((r) => (
              <li key={r.requestId} className="flex flex-wrap gap-3 py-2">
                <span className="flex-1">
                  {ACTION_LABELS[r.action]} — raised by{" "}
                  {r.raisedBy === viewerId ? "you" : ACTOR_NAMES[r.raisedBy]} ·
                  sent to {ACTOR_NAMES[r.reviewerId]}
                </span>
                {r.raisedBy === viewerId ? (
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => onCancelRequest(r.requestId)}
                  >
                    Withdraw
                  </Button>
                ) : null}
              </li>
            ))}
          </ul>
        </Block>
      ) : null}

      <Block
        title="Timeline"
        right={
          <div className="flex gap-2">
            <Button size="sm" variant="ghost" onClick={refresh}>
              Refresh emails
            </Button>
            {writable ? (
              <Button size="sm" variant="outline" onClick={onAddNote}>
                Add a note
              </Button>
            ) : null}
          </div>
        }
      >
        <div
          role="group"
          aria-label="Timeline filter"
          className="mb-2 flex gap-1"
        >
          {TIMELINE_FILTERS.map((f) => (
            <button
              key={f.key}
              type="button"
              aria-pressed={filter === f.key}
              onClick={() => setFilter(f.key)}
              className={`rounded-md px-2 py-0.5 text-xs ${
                filter === f.key
                  ? "bg-slate-900 text-white"
                  : "text-slate-500 hover:bg-slate-100"
              }`}
            >
              {f.label}
            </button>
          ))}
        </div>
        {syncMessage ? (
          <p className="mb-2 text-xs text-slate-500">{syncMessage}</p>
        ) : null}
        {timeline.length === 0 ? (
          <p className="text-sm text-slate-500">Nothing recorded yet.</p>
        ) : (
          <ul className="divide-y divide-slate-100">
            {timeline.map(({ kind, item }) =>
              kind === "note" ? (
                <NoteRow
                  key={item.noteId}
                  note={item}
                  revoked={revokedNoteIds.has(item.noteId)}
                  onRevoke={writable ? onRevoke : null}
                />
              ) : (
                <EmailRow
                  key={item.messageId}
                  email={item}
                  personName={person.name}
                />
              ),
            )}
          </ul>
        )}
        {person.identity === "internal" ? (
          <p className="mt-2 text-xs text-slate-500">
            Reminders to internal members go out on Teams, which Purrf does not
            see — they show up here only as the notes written about them.
          </p>
        ) : null}
      </Block>

      <Block title="Participation history">
        <ul className="divide-y divide-slate-100 text-sm">
          {history.map(({ participant, round: r, pair }) => (
            <li key={participant.participantId} className="flex gap-4 py-2">
              <span className="w-56 shrink-0">{r?.name}</span>
              <span className="w-20 shrink-0 text-slate-600">
                {participant.role}
              </span>
              <span className="w-28 shrink-0 text-slate-600">
                {participant.approvalStatus}
              </span>
              <span className="flex-1 text-slate-600">
                {pair ? (
                  <button
                    type="button"
                    className="underline-offset-2 hover:underline"
                    onClick={() => onOpenPair(pair.pairId)}
                  >
                    {pair.mentorId === participant.userId
                      ? pair.menteeName
                      : pair.mentorName}
                  </button>
                ) : (
                  "—"
                )}
              </span>
              <span className="w-16 shrink-0 text-right text-slate-600">
                {pair ? `${pair.completed}/${pair.required}` : "—"}
              </span>
            </li>
          ))}
        </ul>
        <p className="mt-2 text-xs text-slate-500">
          Ordered by the round&apos;s end date, not by round id — ids do not run
          in time order.
        </p>
      </Block>

      {can("mentorship.feedback.read") ? (
        <Block title="Feedback">
          {history.filter(
            ({ participant }) => feedback[participant.participantId],
          ).length === 0 ? (
            <p className="text-sm text-slate-500">Nothing submitted yet.</p>
          ) : (
            history
              .filter(({ participant }) => feedback[participant.participantId])
              .map(({ participant, round: r }) => {
                const f = feedback[participant.participantId];
                return (
                  <div key={participant.participantId} className="mb-4">
                    <p className="text-sm font-medium">
                      {r?.name} · programme rating {f.programRating}/5
                    </p>
                    <p className="mt-1 text-sm text-slate-700">
                      <span className="text-slate-500">Most valuable: </span>
                      {f.mostValuable}
                    </p>
                    <p className="text-sm text-slate-700">
                      <span className="text-slate-500">Challenges: </span>
                      {f.challenges}
                    </p>
                    {f.partnerFeedback.map((pf) => (
                      <p
                        key={pf.partnerName}
                        className="mt-2 text-sm text-slate-700"
                      >
                        <span className="text-slate-500">
                          {person.name}&apos;s feedback about {pf.partnerName}
                          :{" "}
                        </span>
                        {pf.rating}/5 — &ldquo;{pf.text}&rdquo;
                      </p>
                    ))}
                  </div>
                );
              })
          )}
          <p className="mt-1 text-xs text-slate-500">
            The label always says whose opinion this is. On this page it is what{" "}
            {person.name} wrote about a partner — never what a partner wrote
            about {person.name}, which nobody but an admin ever sees.
          </p>
        </Block>
      ) : null}
    </div>
  );
};

export default ParticipantDetailPage;
