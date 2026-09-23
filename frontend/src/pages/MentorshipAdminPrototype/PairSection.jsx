import { Badge } from "@/components/ui/badge";
import MeetingLogTable from "@/pages/MentorshipAdminPrototype/MeetingLogTable";

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
 * One pair, on the page of either person in it: its state in the header and
 * its meeting log, in the console's existing format, below. A mentor
 * carrying two mentees has two of these, one log each — meetings are counted
 * per pair and never added up.
 *
 * Nothing else lives here. A no show or a partner change is a fact about a
 * person, shown as a badge beside their status, and what happened is on
 * their timeline.
 *
 * @returns {JSX.Element}
 */
const PairSection = ({
  pair,
  person,
  round,
  meetings,
  writable,
  open,
  onToggle,
  onSaveMeetings,
  onMarkFirstContact,
}) => {
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
            disabled={!writable || pair.status !== "active"}
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
        </>
      ) : null}
    </section>
  );
};

export default PairSection;
