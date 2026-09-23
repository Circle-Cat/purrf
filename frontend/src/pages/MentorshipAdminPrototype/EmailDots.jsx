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

const describe = (step, s) => {
  if (s.state === "not_sent") return `${step.label}: not sent`;
  if (s.state === "failed") return `${step.label}: failed on ${s.at}`;
  if (s.state === "replied") return `${step.label}: replied ${s.at}`;
  return `${step.label}: sent${s.channel === "teams" ? " on Teams" : ""} ${s.at}`;
};

/**
 * EmailDots
 *
 * One dot per email of the round, in the order they go out, so a row says
 * at a glance how far someone's correspondence has got. Each dot names its
 * email and state; "T" marks one sent on Teams, which counts as sent. Pressing
 * a dot opens the person's timeline showing emails only.
 *
 * @param {{person: {userId: number, roundId: number}, registered: boolean, emails: object[], notes: object[], onOpen: () => void}} props
 * @returns {JSX.Element}
 */
const EmailDots = ({ person, registered, emails, notes, onOpen }) => (
  <span className="inline-flex flex-wrap gap-1">
    {stepsFor(registered).map((step) => {
      const s = stepState(step, person, emails, notes);
      const text = describe(step, s);
      return (
        <button
          key={step.key}
          type="button"
          aria-label={text}
          title={text}
          onClick={onOpen}
          className={`flex h-5 min-w-5 items-center justify-center rounded-full px-1 text-[10px] leading-none ${LOOK[s.state]}`}
        >
          {s.channel === "teams" ? "T" : s.state === "failed" ? "!" : ""}
        </button>
      );
    })}
  </span>
);

export default EmailDots;
