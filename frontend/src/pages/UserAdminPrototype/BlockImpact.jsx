import { AlertTriangle } from "lucide-react";

/**
 * BlockImpact
 *
 * The pre-flight shown before a block is requested or applied.
 *
 * It states what a block does *and* what it leaves alone. Blocking rejects
 * every application and cancels upcoming interviews, but it does not end a
 * mentorship pair or cancel mentorship meetings — so those are listed under
 * their own heading and explicitly marked untouched. A screen that showed
 * only the first half would read as "everything is handled", which is the
 * mistake this panel exists to prevent.
 *
 * @param {{impact: object}} props
 * @returns {JSX.Element}
 */
const BlockImpact = ({ impact }) => (
  <div className="space-y-3 rounded-md border border-slate-200 bg-slate-50 p-3 text-sm">
    <div>
      <p className="font-medium text-slate-900">Applying this will</p>
      <ul className="mt-1 list-disc space-y-0.5 pl-5 text-slate-700">
        <li>
          Reject and tag {impact.applications} application
          {impact.applications === 1 ? "" : "s"}, including any already hired
        </li>
        <li>Lock the person out of all of Purrf until unblocked</li>
        {impact.interviews.length > 0 ? (
          <li>
            Cancel {impact.interviews.length} upcoming interview
            {impact.interviews.length === 1 ? "" : "s"}:
            <ul className="mt-1 list-none space-y-0.5 pl-0 text-xs text-slate-600">
              {impact.interviews.map((line) => (
                <li key={line}>· {line}</li>
              ))}
            </ul>
          </li>
        ) : (
          <li>Cancel no interviews — none are scheduled</li>
        )}
      </ul>
    </div>

    <div className="flex gap-2 rounded-md border border-amber-300 bg-amber-50 p-2">
      <AlertTriangle size={16} className="mt-0.5 shrink-0 text-amber-700" />
      <div>
        <p className="font-medium text-amber-900">Will NOT be touched</p>
        {impact.mentorshipPairs === 0 &&
        impact.mentorshipMeetings.length === 0 ? (
          <p className="mt-0.5 text-amber-900">
            No mentorship pair or meeting for this person.
          </p>
        ) : (
          <>
            <ul className="mt-1 list-none space-y-0.5 text-amber-900">
              <li>
                · {impact.mentorshipPairs} mentorship pair
                {impact.mentorshipPairs === 1 ? "" : "s"} stays ACTIVE
              </li>
              {impact.mentorshipMeetings.map((line) => (
                <li key={line}>· {line} stays on both calendars</li>
              ))}
            </ul>
            <p className="mt-1 text-xs text-amber-800">
              The mentor is not notified. Handle this separately.
            </p>
          </>
        )}
      </div>
    </div>

    <p className="text-xs text-slate-600">
      Unblocking later restores access, but does not reinstate applications,
      interviews, or mentorship eligibility. Treat this as permanent.
    </p>
  </div>
);

export default BlockImpact;
