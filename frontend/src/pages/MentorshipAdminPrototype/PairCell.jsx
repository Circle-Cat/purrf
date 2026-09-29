import { attendanceIssuesOf } from "@/pages/MentorshipAdminPrototype/attendance";

/**
 * PairCell
 *
 * A person's current pairs, inside their own row — there is no separate pair
 * table. A mentee has at most one active pair a round, so their row carries
 * that pair's facts, first contact included: it is the mentee who reaches out,
 * and marking it is marking them. A mentor can carry several mentees and gets
 * one line per pair, still in one row. Pairs that ended this round are listed
 * too, greyed and marked Ended with the count they stopped at, after the
 * active ones — so a mentee who changed partner shows both. The partner's
 * name is not a link: the one way in is the person's own name, and their page
 * holds every pair they are in.
 *
 * An active pair whose synced meetings show an attendance anomaly turns red,
 * with a red mark between the partner's name and the count, and the anomalies in its tooltip. Only the
 * pair's line changes, not the row: a mentor's other pairs stay as they are.
 *
 * First contact is kept on the pair rather than the person so that a mentee
 * who changes partner starts again at "not yet" with the new mentor.
 *
 * @param {{person: object, pairs: object[], meetings: object[], writable: boolean, onMarkFirstContact: (pairId: number) => void}} props
 * @returns {JSX.Element}
 */
const PairCell = ({
  person,
  pairs,
  meetings = [],
  writable,
  onMarkFirstContact,
}) => {
  const mine = pairs
    .filter((p) => p.mentorId === person.userId || p.menteeId === person.userId)
    .sort(
      (a, b) => Number(b.status === "active") - Number(a.status === "active"),
    );
  if (mine.length === 0) return <span className="text-slate-400">—</span>;

  return (
    <ul className="space-y-1">
      {mine.map((pair) => {
        const isMentee = pair.menteeId === person.userId;
        const partner = isMentee ? pair.mentorName : pair.menteeName;
        const contacted = pair.firstContactConfirmedAt;
        const ended = pair.status !== "active";
        const issues = ended ? [] : attendanceIssuesOf(pair, meetings);
        return (
          <li
            key={pair.pairId}
            aria-label={`Pair ${pair.mentorName} and ${pair.menteeName}`}
            className={`flex flex-wrap items-center gap-x-2 gap-y-1 text-xs ${
              ended ? "text-slate-400" : issues.length ? "text-red-700" : ""
            }`}
          >
            <span
              className={
                ended
                  ? ""
                  : issues.length
                    ? "font-medium"
                    : "font-medium text-slate-800"
              }
            >
              with {partner}
            </span>
            {ended ? (
              <span className="rounded border border-slate-200 px-1 text-[10px]">
                Ended
              </span>
            ) : null}
            {issues.length ? (
              <span
                role="img"
                aria-label={`Attendance issues: ${issues.join(", ")}`}
                title={issues.join("\n")}
                className="inline-flex h-4 w-4 cursor-help items-center justify-center rounded-full bg-red-600 text-[10px] font-bold text-white"
              >
                !
              </span>
            ) : null}
            <span className={ended || issues.length ? "" : "text-slate-500"}>
              Meetings {pair.completed}/{pair.required}
            </span>
            {isMentee && !ended ? (
              <button
                type="button"
                aria-label={
                  contacted
                    ? `First contact confirmed ${contacted} — ${person.name}`
                    : `Mark first contact — ${person.name}`
                }
                disabled={!writable}
                onClick={() => onMarkFirstContact(pair.pairId)}
                className={`rounded px-1.5 py-0.5 ${
                  contacted
                    ? "bg-emerald-100 text-emerald-800"
                    : "border border-slate-300 text-slate-500 hover:bg-slate-100"
                } ${writable ? "" : "cursor-default opacity-60"}`}
              >
                {contacted
                  ? `First contact ✓ ${contacted}`
                  : "First contact — mark"}
              </button>
            ) : null}
          </li>
        );
      })}
    </ul>
  );
};

export default PairCell;
