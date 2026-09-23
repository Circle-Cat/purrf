import { useEffect, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import FlagBadges from "@/pages/MentorshipAdminPrototype/FlagBadges";
import PairSection from "@/pages/MentorshipAdminPrototype/PairSection";
import MeetingLogTable from "@/pages/MentorshipAdminPrototype/MeetingLogTable";
import {
  ACTION_LABELS,
  ACTOR_NAMES,
  NOTE_KIND,
  NOTE_LABELS,
  TEMPLATE_LABELS,
} from "@/pages/MentorshipAdminPrototype/mockData";

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
          <Badge
            variant={
              kind === "decided" && note.tag !== "matching_exemption"
                ? "destructive"
                : "secondary"
            }
          >
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
 * One email on the timeline — a message Purrf sent (or tried to, and failed),
 * or a reply pulled back in.
 *
 * The template name leads because it answers the question people come here
 * with ("did she get the mid-term reminder?"); the body is only a glimpse.
 */
const EmailRow = ({ email, personName }) => (
  <li className="flex gap-3 py-2">
    <span className="w-40 shrink-0 text-xs">
      {email.direction === "in" ? (
        <Badge variant="outline">Reply</Badge>
      ) : email.status === "failed" ? (
        <Badge
          variant="outline"
          className="border-amber-400 bg-amber-50 text-amber-900"
        >
          Failed to send
        </Badge>
      ) : (
        <Badge variant="outline">Email sent</Badge>
      )}
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
 * The timeline is notes and emails together, newest first, with no filter by
 * kind. "What has happened with her" is one question; answering it from two
 * lists means interleaving them by date in your head.
 *
 * Each pair this person is in this round is a section of its own, with its
 * meeting log. A mentor carrying two mentees has two sections and two logs:
 * adding them up would invent a number that does not exist.
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
  onAddNote,
  onRaise,
  onCompose,
  flags,
  revokedNoteIds,
  requests,
  viewerId,
  onCancelRequest,
  onRevoke,
  exempt,
  historyIssues = [],
  onRequestExemption,
  openPairId,
  pairMeetings,
  onSaveMeetings,
  onMarkFirstContact,
  blocked = false,
  onRequestBlock,
  onMarkNotified,
  readOnly = false,
}) => {
  // The pair that was clicked to get here opens; otherwise the first does.
  const [openPairs, setOpenPairs] = useState(() => {
    if (openPairId) return [openPairId];
    const first = pairs.find(
      (p) =>
        p.roundId === person?.roundId &&
        p.status === "active" &&
        (p.mentorId === person?.userId || p.menteeId === person?.userId),
    );
    return first ? [first.pairId] : [];
  });
  const [syncMessage, setSyncMessage] = useState(null);
  const [openRounds, setOpenRounds] = useState([]);
  // Arriving from a pair link lands on that pair, not the top of the page.
  useEffect(() => {
    if (!openPairId) return;
    document
      .getElementById(`pair-${openPairId}`)
      ?.scrollIntoView?.({ block: "start" });
  }, [openPairId]);
  if (!person) return null;

  const round = rounds.find((r) => r.id === person.roundId);
  // Active pairs first; an ended one stays readable below them.
  const myPairs = pairs
    .filter(
      (p) =>
        p.roundId === person.roundId &&
        (p.mentorId === person.userId || p.menteeId === person.userId),
    )
    .sort(
      (a, b) => Number(b.status === "active") - Number(a.status === "active"),
    );
  const endOf = (r) => r?.timeline.meetingsCompletionDeadlineAt ?? "";
  const everyRound = participants
    .filter((p) => p.userId === person.userId)
    .map((p) => ({
      participant: p,
      round: rounds.find((r) => r.id === p.roundId),
      pairs: pairs
        .filter(
          (x) =>
            x.roundId === p.roundId &&
            (x.mentorId === p.userId || x.menteeId === p.userId),
        )
        .sort(
          (a, b) =>
            Number(b.status === "active") - Number(a.status === "active"),
        ),
    }))
    .sort((a, b) => endOf(b.round).localeCompare(endOf(a.round)));
  // Only rounds that ended before the one on this page: this round is the
  // page itself, and a later one is not "history" from here.
  const history = everyRound.filter(
    (h) => endOf(h.round) && endOf(h.round) < endOf(round),
  );

  const registered = person.participantId != null;

  /** Notes and emails of one round, newest first. */
  const timelineOf = (roundId) =>
    [
      ...notes
        .filter((n) => n.userId === person.userId && n.roundId === roundId)
        .map((n) => ({ kind: "note", at: n.createdAt, item: n })),
      ...emails
        .filter((e) => e.roundId === roundId)
        .map((e) => ({ kind: "email", at: e.at, item: e })),
    ].sort((a, b) => b.at.localeCompare(a.at));
  const timeline = timelineOf(person.roundId);
  const renderTimeline = (entries, revoke) =>
    entries.length === 0 ? (
      <p className="text-sm text-slate-500">Nothing recorded yet.</p>
    ) : (
      <ul className="divide-y divide-slate-100">
        {entries.map(({ kind, item }) =>
          kind === "note" ? (
            <NoteRow
              key={item.noteId}
              note={item}
              revoked={revokedNoteIds.has(item.noteId)}
              onRevoke={revoke}
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
    );

  /** What they wrote in one round's feedback form. */
  const renderFeedback = (f) => (
    <div>
      <p className="text-sm font-medium">
        Programme rating {f.programRating}/5
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
        <p key={pf.partnerName} className="mt-2 text-sm text-slate-700">
          <span className="text-slate-500">
            {person.name}&apos;s feedback about {pf.partnerName}:{" "}
          </span>
          {pf.rating}/5 — &ldquo;{pf.text}&rdquo;
        </p>
      ))}
    </div>
  );

  const refresh = () => {
    const count = onRefreshEmails();
    setSyncMessage(
      count === 0
        ? "Checked the mailbox — no new replies."
        : `Checked the mailbox — ${count} new ${count === 1 ? "reply" : "replies"}.`,
    );
  };
  // An earlier round is a record: it can be read, not changed.
  const writable = can("mentorship.admin.write") && !readOnly;
  /** Flags that still stand from one round, as `{tag: count}`. */
  const flagsIn = (roundId) => {
    const out = {};
    notes
      .filter(
        (n) =>
          n.userId === person.userId &&
          n.roundId === roundId &&
          NOTE_KIND[n.tag] === "decided" &&
          n.tag !== "matching_exemption" &&
          !revokedNoteIds.has(n.noteId),
      )
      .forEach((n) => {
        out[n.tag] = (out[n.tag] ?? 0) + 1;
      });
    return out;
  };

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

      {readOnly ? (
        <p className="border-t border-slate-200 bg-slate-50 px-5 py-2 text-xs text-slate-600">
          An earlier round — read only. Nothing here can be changed; what
          happens next is written on the current round.
        </p>
      ) : null}
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
              {blocked ? null : (
                <Button size="sm" variant="outline" onClick={onRequestBlock}>
                  Block from Purrf
                </Button>
              )}
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
          <span>Training {person.onboardingDone ? "done" : "not done"}</span>
          {myPairs.length === 0 ? (
            <span className="text-slate-500">No pair this round</span>
          ) : null}
        </div>
        {registered && historyIssues.length > 0 ? (
          <div
            className={`mt-3 rounded-md border px-3 py-2 text-sm ${
              exempt
                ? "border-emerald-200 bg-emerald-50 text-emerald-900"
                : "border-amber-200 bg-amber-50 text-amber-900"
            }`}
          >
            <p className="font-medium">
              {exempt
                ? "Exempted for this round's matching"
                : "Needs an exemption before being matched this round"}
            </p>
            <ul className="mt-1 list-disc pl-5 text-xs">
              {historyIssues.map((issue) => (
                <li key={issue}>{issue}</li>
              ))}
            </ul>
            {!exempt && writable ? (
              <Button
                size="sm"
                variant="outline"
                className="mt-2"
                onClick={onRequestExemption}
              >
                Request exemption
              </Button>
            ) : null}
          </div>
        ) : null}
        {myPairs.map((pair) => (
          <PairSection
            key={pair.pairId}
            pair={pair}
            person={person}
            round={round}
            meetings={pairMeetings(pair.pairId)}
            writable={writable}
            open={openPairs.includes(pair.pairId)}
            onToggle={() =>
              setOpenPairs((all) =>
                all.includes(pair.pairId)
                  ? all.filter((id) => id !== pair.pairId)
                  : [...all, pair.pairId],
              )
            }
            onSaveMeetings={(batch) => onSaveMeetings(pair.pairId, batch)}
            onMarkFirstContact={() => onMarkFirstContact(pair.pairId)}
          />
        ))}
      </Block>

      {requests.some((r) => r.status === "pending") ? (
        <Block title="Waiting on a decision">
          <ul className="divide-y divide-slate-100 text-sm">
            {requests
              .filter((r) => r.status === "pending")
              .map((r) => (
                <li key={r.requestId} className="flex flex-wrap gap-3 py-2">
                  <span className="flex-1">
                    {ACTION_LABELS[r.action]}
                    {r.targetLabel && r.targetLabel !== person.name
                      ? ` (${r.targetLabel})`
                      : ""}{" "}
                    — raised by{" "}
                    {r.raisedBy === viewerId ? "you" : ACTOR_NAMES[r.raisedBy]}{" "}
                    · sent to {ACTOR_NAMES[r.reviewerId]}
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

      {requests.some((r) => r.status === "invalidated") ? (
        <Block title="Not applied">
          <ul className="divide-y divide-slate-100 text-sm">
            {requests
              .filter((r) => r.status === "invalidated")
              .map((r) => (
                <li key={r.requestId} className="py-2">
                  {ACTION_LABELS[r.action]} — approved by{" "}
                  {ACTOR_NAMES[r.decidedBy]} on {r.decidedAt}, but not applied:{" "}
                  <span className="text-amber-900">{r.invalidReason}</span>
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
              <>
                <Button size="sm" variant="outline" onClick={onMarkNotified}>
                  Mark as notified
                </Button>
                <Button size="sm" variant="outline" onClick={onAddNote}>
                  Add a note
                </Button>
              </>
            ) : null}
          </div>
        }
      >
        {syncMessage ? (
          <p className="mb-2 text-xs text-slate-500">{syncMessage}</p>
        ) : null}
        {renderTimeline(timeline, writable ? onRevoke : null)}
        {person.identity === "internal" ? (
          <p className="mt-2 text-xs text-slate-500">
            Reminders to internal members go out on Teams, which Purrf does not
            see — they show up here only as the notes written about them.
          </p>
        ) : null}
      </Block>

      {can("mentorship.feedback.read") ? (
        <Block title="Feedback">
          {feedback[person.participantId] ? (
            renderFeedback(feedback[person.participantId])
          ) : (
            <p className="text-sm text-slate-500">
              Nothing submitted for this round yet. Earlier rounds&apos;
              feedback is under each round in the participation history.
            </p>
          )}
          <p className="mt-1 text-xs text-slate-500">
            The label always says whose opinion this is. On this page it is what{" "}
            {person.name} wrote about a partner — never what a partner wrote
            about {person.name}, which nobody but an admin ever sees.
          </p>
        </Block>
      ) : null}

      <Block title="Participation history">
        {history.length === 0 ? (
          <p className="text-sm text-slate-500">
            No earlier rounds — this is the first time they have taken part.
          </p>
        ) : null}
        <ul className="divide-y divide-slate-100 text-sm">
          {history.map(({ participant, round: r, pairs: theirs }) => {
            const expanded = openRounds.includes(participant.roundId);
            return (
              <li key={participant.participantId} className="py-2">
                <div className="flex gap-4">
                  <span className="w-56 shrink-0">
                    <button
                      type="button"
                      aria-expanded={expanded}
                      className="text-left font-medium"
                      onClick={() =>
                        setOpenRounds((all) =>
                          expanded
                            ? all.filter((id) => id !== participant.roundId)
                            : [...all, participant.roundId],
                        )
                      }
                    >
                      {expanded ? "▾" : "▸"} {r?.name}
                    </button>
                    <FlagBadges flags={flagsIn(participant.roundId)} />
                  </span>
                  <span className="w-20 shrink-0 text-slate-600">
                    {participant.role}
                  </span>
                  <span className="w-28 shrink-0 text-slate-600">
                    {participant.approvalStatus}
                  </span>
                  <ul className="flex-1 space-y-0.5 text-slate-600">
                    {theirs.length === 0 ? <li>—</li> : null}
                    {theirs.map((pair) => (
                      <li
                        key={pair.pairId}
                        className={`flex gap-4 ${
                          pair.status === "active" ? "" : "text-slate-400"
                        }`}
                      >
                        <span className="flex-1">
                          {pair.mentorId === participant.userId
                            ? pair.menteeName
                            : pair.mentorName}
                          {pair.status === "active" ? "" : " · ended"}
                        </span>
                        <span className="w-16 shrink-0 text-right">
                          {pair.completed}/{pair.required}
                        </span>
                      </li>
                    ))}
                  </ul>
                </div>
                {expanded ? (
                  // Read only: an earlier round is a record.
                  <div className="mt-2 rounded-md bg-slate-50 px-3 py-2">
                    {theirs.map((pair) => (
                      <div key={pair.pairId} className="mb-3">
                        <p className="mb-1 text-xs font-medium text-slate-600">
                          Meeting log — with{" "}
                          {pair.mentorId === participant.userId
                            ? pair.menteeName
                            : pair.mentorName}
                        </p>
                        <MeetingLogTable
                          roundVersion={null}
                          mentorName={pair.mentorName}
                          menteeName={pair.menteeName}
                          meetings={pairMeetings(pair.pairId)}
                          onSave={() => {}}
                        />
                      </div>
                    ))}
                    <p className="mb-1 text-xs font-medium text-slate-600">
                      Timeline
                    </p>
                    {renderTimeline(timelineOf(participant.roundId), null)}
                    {can("mentorship.feedback.read") ? (
                      <>
                        <p className="mb-1 mt-3 text-xs font-medium text-slate-600">
                          Feedback
                        </p>
                        {feedback[participant.participantId] ? (
                          renderFeedback(feedback[participant.participantId])
                        ) : (
                          <p className="text-sm text-slate-500">
                            Nothing submitted.
                          </p>
                        )}
                      </>
                    ) : null}
                  </div>
                ) : null}
              </li>
            );
          })}
        </ul>
        <p className="mt-2 text-xs text-slate-500">
          Ordered by the round&apos;s end date, not by round id — ids do not run
          in time order.
        </p>
      </Block>
    </div>
  );
};

export default ParticipantDetailPage;
