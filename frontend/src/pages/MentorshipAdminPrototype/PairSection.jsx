import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import MeetingLogTable from "@/pages/MentorshipAdminPrototype/MeetingLogTable";
import {
  ACTION_LABELS,
  ACTOR_NAMES,
  NOTE_KIND,
  NOTE_LABELS,
} from "@/pages/MentorshipAdminPrototype/mockData";

const Block = ({ title, right, children }) => (
  <section className="border-t border-slate-100 px-4 py-3">
    <header className="mb-3 flex items-center gap-3">
      <h3 className="text-sm font-semibold">{title}</h3>
      <div className="ml-auto">{right}</div>
    </header>
    {children}
  </section>
);

/**
 * PairSection
 *
 * One pair, on the page of either person in it: the meeting log in the
 * console's existing format, the notes about this pair, and how its status
 * got here. A mentor carrying two mentees has two of these, one log each —
 * meetings are counted per pair and never added up.
 *
 * This is where notes with a pair id are read, which is the reason notes carry
 * one. The same pair appears on both people's pages from the same records,
 * so a change on one shows on the other.
 *
 * @returns {JSX.Element}
 */
const PairSection = ({
  pair,
  person,
  round,
  meetings,
  notes,
  requests,
  can,
  open,
  onToggle,
  onAddNote,
  onRaise,
  onSaveMeetings,
  onMarkFirstContact,
}) => {
  const writable = can("mentorship.admin.write");
  const decided = requests.filter((r) => r.status !== "pending");
  const isMentee = pair.menteeId === person.userId;
  const partner = isMentee ? pair.mentorName : pair.menteeName;

  return (
    <section
      id={`pair-${pair.pairId}`}
      className="mt-3 rounded-md border border-slate-200"
    >
      <header className="flex flex-wrap items-center gap-3 px-4 py-3">
        <button
          type="button"
          aria-expanded={open}
          onClick={onToggle}
          className="text-left text-sm font-semibold"
        >
          {open ? "▾" : "▸"} with {partner}
        </button>
        <Badge variant={pair.status === "active" ? "secondary" : "outline"}>
          {pair.status}
        </Badge>
        <span className="text-xs text-slate-500">
          Meetings {pair.completed}/{pair.required}
        </span>
        {isMentee ? (
          <button
            type="button"
            disabled={!writable}
            onClick={onMarkFirstContact}
            aria-label={
              pair.firstContactConfirmedAt
                ? `First contact confirmed ${pair.firstContactConfirmedAt} — ${person.name}`
                : `Mark first contact — ${person.name}`
            }
            className={`rounded px-1.5 py-0.5 text-xs ${
              pair.firstContactConfirmedAt
                ? "bg-emerald-100 text-emerald-800"
                : "border border-slate-300 text-slate-500 hover:bg-slate-100"
            }`}
          >
            {pair.firstContactConfirmedAt
              ? `First contact ✓ ${pair.firstContactConfirmedAt}`
              : "First contact — mark"}
          </button>
        ) : null}
        {writable && pair.status === "active" ? (
          <Button
            size="sm"
            variant="outline"
            className="ml-auto"
            aria-label={`Change partner — ${pair.mentorName} and ${pair.menteeName}`}
            onClick={onRaise}
          >
            Change partner
          </Button>
        ) : null}
      </header>

      {open ? (
        <>
          <Block title="Meeting log">
            <MeetingLogTable
              roundVersion={writable ? round?.version : null}
              mentorName={pair.mentorName}
              menteeName={pair.menteeName}
              meetings={meetings}
              onSave={onSaveMeetings}
            />
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
                        <Badge
                          variant={
                            NOTE_KIND[n.tag] === "decided"
                              ? "destructive"
                              : "secondary"
                          }
                        >
                          {NOTE_LABELS[n.tag]}
                        </Badge>
                      ) : (
                        <span className="text-slate-400">Note</span>
                      )}
                    </span>
                    <span className="w-40 shrink-0 text-xs text-slate-500">
                      {ACTOR_NAMES[n.authorId]} · {n.createdAt}
                    </span>
                    <span className="flex-1 text-sm text-slate-700">
                      {n.body || <em className="text-slate-400">No comment</em>}
                    </span>
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
                      {r.decisionNote ? ` — ${r.decisionNote}` : ""}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </Block>
        </>
      ) : null}
    </section>
  );
};

export default PairSection;
