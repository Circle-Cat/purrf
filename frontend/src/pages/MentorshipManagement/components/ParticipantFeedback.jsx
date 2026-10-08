import { unresolvedPersonLabel } from "@/pages/Recruiting/components/personLabel";

// Same as the round's Feedback page: the ID goes beside the name.
const partnerLabel = (entry) =>
  entry.partnerName
    ? `${entry.partnerName} (ID ${entry.partnerId})`
    : unresolvedPersonLabel(entry.partnerId);

const partnerLine = (entry) => {
  const parts = [partnerLabel(entry) + ":"];
  if (entry.rating != null) parts.push(`${entry.rating}/5`);
  const head = parts.join(" ");
  return entry.feedback ? `${head} — “${entry.feedback}”` : head;
};

/**
 * What this person sent in the round's feedback, in the order the form asks
 * it. What they wrote about a partner is their view of that partner. Shown
 * only for someone the feedback is asked of (they had a pair this round).
 *
 * @param {{feedback: Object|null}} props
 */
const ParticipantFeedback = ({ feedback }) => {
  if (feedback == null) return null;
  return (
    <section>
      <h3 className="mb-2 text-sm font-semibold">Feedback</h3>
      {!feedback.hasSubmitted ? (
        <p className="text-sm text-muted-foreground">Not sent yet.</p>
      ) : (
        <dl className="grid grid-cols-[max-content_1fr] gap-x-4 gap-y-2 text-sm">
          <dt className="text-slate-500">Most Valuable Aspects</dt>
          <dd className="whitespace-pre-wrap break-words">
            {feedback.mostValuableAspects || "—"}
          </dd>
          <dt className="text-slate-500">Challenges</dt>
          <dd className="whitespace-pre-wrap break-words">
            {feedback.challenges || "—"}
          </dd>
          <dt className="text-slate-500">Program Rating</dt>
          <dd>
            {feedback.programRating != null ? `${feedback.programRating}/5` : "—"}
          </dd>
          <dt className="text-slate-500">About Partners</dt>
          <dd>
            {feedback.partnerFeedback?.length ? (
              <ul className="space-y-1">
                {feedback.partnerFeedback.map((entry, i) => (
                  // Nothing on the write side stops a partner appearing twice.
                  <li key={`${entry.partnerId}-${i}`} className="break-words">
                    {partnerLine(entry)}
                  </li>
                ))}
              </ul>
            ) : (
              "—"
            )}
          </dd>
        </dl>
      )}
    </section>
  );
};

export default ParticipantFeedback;
