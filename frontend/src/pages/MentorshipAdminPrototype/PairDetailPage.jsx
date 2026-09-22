import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  ACTION_LABELS,
  ACTOR_NAMES,
  MEETING_TAG_LABELS,
  NOTE_LABELS,
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
 * PairDetailPage
 *
 * Everything that belongs to a *pairing*: the meeting log, whether first
 * contact happened, the notes about this pair, and how its status got here.
 *
 * This page is the reason notes carry an optional pair id at all. Without it
 * that column would have nowhere to be read from, and a nullable foreign key
 * nothing ever filters on is just a field waiting to be deleted.
 *
 * @returns {JSX.Element}
 */
const PairDetailPage = ({
  pair,
  round,
  meetings,
  notes,
  requests,
  can,
  onBack,
  onAddNote,
}) => {
  if (!pair) return null;
  const writable = can("mentorship.admin.write");
  const decided = requests.filter((r) => r.status !== "pending");

  return (
    <div className="rounded-lg border border-slate-200 bg-white">
      <header className="flex flex-wrap items-center gap-3 px-5 py-4">
        <Button size="sm" variant="ghost" onClick={onBack}>
          ← Pairs
        </Button>
        <div>
          <h2 className="text-base font-semibold">
            {pair.mentorName} &nbsp;↔&nbsp; {pair.menteeName}
          </h2>
          <p className="mt-1 flex flex-wrap items-center gap-3 text-xs text-slate-500">
            <span>{round?.name}</span>
            <Badge variant={pair.status === "active" ? "secondary" : "outline"}>
              {pair.status}
            </Badge>
            <span>
              First contact{" "}
              {pair.firstContactConfirmedAt
                ? `confirmed ${pair.firstContactConfirmedAt}`
                : "not confirmed"}
            </span>
            <span>
              {pair.completed}/{pair.required} meetings
            </span>
          </p>
        </div>
      </header>

      <Block
        title="Meeting log"
        right={
          writable ? (
            <Button size="sm" variant="outline">
              Add a meeting
            </Button>
          ) : null
        }
      >
        {meetings.length === 0 ? (
          <p className="text-sm text-slate-500">No meetings recorded yet.</p>
        ) : (
          <ul className="divide-y divide-slate-100 text-sm">
            {meetings.map((m) => (
              <li key={m.meetingId} className="flex flex-wrap gap-3 py-2">
                <span className="w-24 shrink-0">{m.date}</span>
                <span className="w-32 shrink-0 text-slate-600">
                  {m.start}–{m.end}
                </span>
                <span className="w-24 shrink-0">
                  {m.completed ? "Held" : "Not held"}
                </span>
                <span className="flex-1 space-x-1">
                  {m.tags.map((t) => (
                    <Badge key={t} variant="outline">
                      {MEETING_TAG_LABELS[t]}
                    </Badge>
                  ))}
                </span>
                {writable ? (
                  <Button size="sm" variant="ghost">
                    Edit
                  </Button>
                ) : null}
              </li>
            ))}
          </ul>
        )}
        <p className="mt-2 text-xs text-slate-500">
          Meetings live here rather than on either person&apos;s page: a mentor
          carrying two mentees has two logs, not one.
        </p>
      </Block>

      <Block
        title="Notes about this pair"
        right={
          writable ? (
            <Button size="sm" variant="outline" onClick={onAddNote}>
              Add a note
            </Button>
          ) : null
        }
      >
        {notes.length === 0 ? (
          <p className="text-sm text-slate-500">Nothing recorded yet.</p>
        ) : (
          <ul className="divide-y divide-slate-100">
            {notes.map((n) => (
              <li key={n.noteId} className="flex gap-3 py-2">
                <span className="w-44 shrink-0 text-xs">
                  {n.tag ? (
                    <Badge variant="destructive">{NOTE_LABELS[n.tag]}</Badge>
                  ) : (
                    <span className="text-slate-400">Note</span>
                  )}
                </span>
                <span className="w-40 shrink-0 text-xs text-slate-500">
                  {ACTOR_NAMES[n.authorId]} · {n.createdAt}
                </span>
                <span className="flex-1 text-sm text-slate-700">{n.body}</span>
              </li>
            ))}
          </ul>
        )}
      </Block>

      <Block title="Status history">
        {decided.length === 0 ? (
          <p className="text-sm text-slate-500">
            No status change has been decided for this pair.
          </p>
        ) : (
          <ul className="divide-y divide-slate-100 text-sm">
            {decided.map((r) => (
              <li key={r.requestId} className="flex gap-3 py-2">
                <span className="w-24 shrink-0 text-slate-600">
                  {r.decidedAt}
                </span>
                <span className="flex-1">
                  {ACTION_LABELS[r.action]} — {r.status} · raised by{" "}
                  {ACTOR_NAMES[r.raisedBy]}, decided by{" "}
                  {ACTOR_NAMES[r.decidedBy]}
                </span>
              </li>
            ))}
          </ul>
        )}
      </Block>
    </div>
  );
};

export default PairDetailPage;
