import { useState } from "react";
import { Button } from "@/components/ui/button";
import { feedbackOwedBy } from "@/pages/MentorshipAdminPrototype/feedback";

/**
 * FeedbackPage
 *
 * Everyone's feedback for one round, opened from the Feedback column of the
 * rounds table: who has sent it, who still owes it, and what each person
 * wrote. The list is the people feedback is asked of (see `feedbackOwedBy`),
 * so "Not sent" means somebody who should have.
 *
 * What someone wrote about their partner is labelled "X's feedback about Y":
 * it sits on the writer's row, and nobody reads it as feedback *on* X.
 *
 * @param {object} props
 * @param {object} props.round
 * @param {Array<object>} props.participants - Every round's rows.
 * @param {Array<object>} props.pairs - Every round's pairs.
 * @param {Object<string, object>} props.feedback - Keyed by participant id.
 * @param {Function} props.accountOf
 * @param {Function} props.can
 * @param {Function} props.onBack
 * @param {(userId: number) => void} props.onOpenPerson
 * @returns {JSX.Element}
 */
const FeedbackPage = ({
  round,
  participants,
  pairs,
  feedback,
  accountOf,
  can,
  onBack,
  onOpenPerson,
}) => {
  const [role, setRole] = useState("all");
  const [notSentOnly, setNotSentOnly] = useState(false);

  if (!can("mentorship.feedback.read")) {
    return (
      <div className="rounded-lg border border-slate-200 bg-white px-5 py-4">
        <Button size="sm" variant="ghost" onClick={onBack}>
          ← Mentorship
        </Button>
        <p className="mt-3 text-sm text-slate-600">
          Reading feedback needs the feedback-read permission.
        </p>
      </div>
    );
  }

  const owed = feedbackOwedBy(round, participants, pairs, accountOf);
  const sentCount = owed.filter((p) => feedback[p.participantId]).length;
  const rows = owed
    .filter((p) => role === "all" || p.role === role)
    .filter((p) => !notSentOnly || !feedback[p.participantId])
    .sort((a, b) => a.name.localeCompare(b.name));

  return (
    <div className="rounded-lg border border-slate-200 bg-white">
      <header className="flex flex-wrap items-center gap-3 border-b border-slate-200 px-5 py-4">
        <Button size="sm" variant="ghost" onClick={onBack}>
          ← Mentorship
        </Button>
        <h2 className="text-base font-semibold">Feedback — {round.name}</h2>
        <span className="text-xs text-slate-500">
          {sentCount} of {owed.length} sent
        </span>
      </header>

      <div className="flex flex-wrap items-center gap-3 px-5 py-3">
        <label className="flex items-center gap-2 text-xs text-slate-600">
          Role
          <select
            aria-label="Role"
            value={role}
            onChange={(e) => setRole(e.target.value)}
            className="h-8 rounded-md border border-slate-300 px-2 text-xs"
          >
            <option value="all">All roles</option>
            <option value="mentor">Mentor</option>
            <option value="mentee">Mentee</option>
          </select>
        </label>
        <label className="flex items-center gap-2 text-xs text-slate-600">
          <input
            type="checkbox"
            checked={notSentOnly}
            onChange={(e) => setNotSentOnly(e.target.checked)}
          />
          Not sent only
        </label>
        <span className="text-xs text-slate-500">
          Asked of everyone in a pair this round who has not withdrawn and is
          not blocked.
        </span>
      </div>

      <table className="w-full">
        <thead className="border-y border-slate-200 bg-slate-50">
          <tr className="text-left text-xs font-medium text-slate-500">
            <th className="px-5 py-2">Name</th>
            <th className="px-3 py-2">Role</th>
            <th className="px-3 py-2">Sent</th>
            <th className="px-3 py-2">Programme rating</th>
            <th className="px-3 py-2">Most valuable</th>
            <th className="px-3 py-2">Challenges</th>
            <th className="px-3 py-2">About their partner</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {rows.length === 0 ? (
            <tr>
              <td colSpan={7} className="px-5 py-4 text-sm text-slate-500">
                Nobody here.
              </td>
            </tr>
          ) : (
            rows.map((p) => {
              const f = feedback[p.participantId];
              return (
                <tr key={p.participantId} className="align-top text-sm">
                  <td className="px-5 py-2">
                    <button
                      type="button"
                      className="font-medium underline-offset-2 hover:underline"
                      onClick={() => onOpenPerson(p.userId)}
                    >
                      {p.name}
                    </button>
                    <div className="text-xs text-slate-500">ID {p.userId}</div>
                  </td>
                  <td className="px-3 py-2">{p.role}</td>
                  <td className="px-3 py-2">
                    {f ? (
                      "Sent"
                    ) : (
                      <span className="text-amber-800">Not sent</span>
                    )}
                  </td>
                  <td className="px-3 py-2">
                    {f?.programRating != null ? `${f.programRating}/5` : "—"}
                  </td>
                  <td className="px-3 py-2 text-slate-700">
                    {f?.mostValuable ?? "—"}
                  </td>
                  <td className="px-3 py-2 text-slate-700">
                    {f?.challenges ?? "—"}
                  </td>
                  <td className="px-3 py-2 text-slate-700">
                    {f?.partnerFeedback?.length
                      ? f.partnerFeedback.map((pf) => (
                          <p key={pf.partnerName}>
                            <span className="text-slate-500">
                              {p.name}&apos;s feedback about {pf.partnerName}
                              :{" "}
                            </span>
                            {pf.rating}/5
                            {pf.text ? <> — &ldquo;{pf.text}&rdquo;</> : null}
                          </p>
                        ))
                      : "—"}
                  </td>
                </tr>
              );
            })
          )}
        </tbody>
      </table>
    </div>
  );
};

export default FeedbackPage;
