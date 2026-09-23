import {
  stepState,
  stepsFor,
} from "@/pages/MentorshipAdminPrototype/emailStatus";

const LOOK = {
  replied: "bg-emerald-600 text-white",
  sent: "bg-emerald-200 text-emerald-900",
  failed: "bg-amber-300 text-amber-950",
  not_sent: "border border-slate-300 text-slate-400",
};

/** Every dot sits in a slot this wide, so the header's labels line up. */
const SLOT = "w-16 shrink-0 text-center";

const how = (s) =>
  s.channel === "teams"
    ? " on Teams"
    : s.channel === "auto"
      ? " automatically"
      : "";

const describe = (step, s) => {
  if (s.state === "not_sent") return `${step.label}: not sent`;
  if (s.state === "failed") return `${step.label}: failed on ${s.at}`;
  if (s.state === "replied") return `${step.label}: replied ${s.at}`;
  return `${step.label}: sent${how(s)} ${s.at}`;
};

/**
 * What the colours mean, drawn with the very dots the table uses.
 *
 * @returns {JSX.Element}
 */
export const EmailLegend = () => (
  <p className="mb-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-slate-600">
    <span className="font-medium">Emails:</span>
    {[
      { look: LOOK.sent, mark: "", text: "Sent" },
      { look: LOOK.replied, mark: "", text: "Sent and replied" },
      { look: LOOK.sent, mark: "T", text: "Sent on Teams" },
      { look: LOOK.failed, mark: "!", text: "Failed to send" },
      { look: LOOK.not_sent, mark: "", text: "Not sent" },
    ].map((item) => (
      <span key={item.text} className="inline-flex items-center gap-1">
        <span
          className={`flex h-4 w-4 items-center justify-center rounded-full text-[9px] leading-none ${item.look}`}
        >
          {item.mark}
        </span>
        {item.text}
      </span>
    ))}
    <span className="text-slate-400">
      Hover a dot for the date; press it to open the emails.
    </span>
  </p>
);

/**
 * The column header: the name of each email above its dot, in the same slots.
 *
 * @param {{registered: boolean}} props
 * @returns {JSX.Element}
 */
export const EmailDotsHeader = ({ registered }) => (
  <span className="block">
    <span className="block">Emails</span>
    <span className="mt-1 flex items-end text-[10px] font-normal leading-tight text-slate-500">
      {stepsFor(registered).map((step) => (
        <span key={step.key} className={SLOT} title={step.label}>
          {step.short}
        </span>
      ))}
    </span>
  </span>
);

/**
 * EmailDots
 *
 * Two lines. The first says how far someone's correspondence has got — the
 * latest email that went out, and when — and whether anything failed, so a
 * glance down the column answers "where are we with each person". The second
 * is one dot per email of the round, in order, under the header's labels:
 * that is where to see which one is missing. "T" marks an email sent on
 * Teams, which counts as sent; "!" one that failed. Pressing a dot opens the
 * person's timeline showing emails only.
 *
 * @param {{person: {userId: number, roundId: number}, registered: boolean, emails: object[], notes: object[], notifications: object[], onOpen: () => void}} props
 * @returns {JSX.Element}
 */
const EmailDots = ({
  person,
  registered,
  emails,
  notes,
  notifications,
  onOpen,
}) => {
  const steps = stepsFor(registered).map((step) => ({
    step,
    s: stepState(step, person, emails, notes, notifications),
  }));
  const gone = steps.filter(
    ({ s }) => s.state === "sent" || s.state === "replied",
  );
  // The latest by date; on the same day, the one later in the round.
  const latest = gone.reduce(
    (best, cur) => (!best || cur.s.at >= best.s.at ? cur : best),
    null,
  );
  const failed = steps.filter(({ s }) => s.state === "failed").length;

  return (
    <span className="block">
      <span className="block text-xs">
        {latest ? (
          <>
            <span className="font-medium">{latest.step.label}</span> ·{" "}
            {latest.s.at}
            {latest.s.channel === "teams" ? " (Teams)" : ""}
            {latest.s.state === "replied" ? " · replied" : ""}
          </>
        ) : (
          <span className="text-slate-400">Nothing sent yet</span>
        )}
        {failed > 0 ? (
          <span className="ml-2 text-amber-800">⚠ {failed} failed</span>
        ) : null}
      </span>
      <span className="mt-1 flex">
        {steps.map(({ step, s }) => {
          const text = describe(step, s);
          return (
            <span key={step.key} className={SLOT}>
              <button
                type="button"
                aria-label={text}
                title={text}
                onClick={onOpen}
                className={`mx-auto flex h-5 w-5 items-center justify-center rounded-full text-[10px] leading-none ${LOOK[s.state]}`}
              >
                {s.channel === "teams" ? "T" : s.state === "failed" ? "!" : ""}
              </button>
            </span>
          );
        })}
      </span>
    </span>
  );
};

export default EmailDots;
