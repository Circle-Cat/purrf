import { Badge } from "@/components/ui/badge";
import {
  stepState,
  stepsFor,
} from "@/pages/MentorshipAdminPrototype/emailStatus";

const BADGE = {
  replied: {
    text: "Replied",
    className: "border-emerald-600 bg-emerald-600 text-white",
  },
  sent: {
    text: "Notified",
    className: "border-emerald-300 bg-emerald-50 text-emerald-800",
  },
  failed: {
    text: "Failed",
    className: "border-amber-400 bg-amber-50 text-amber-900",
  },
  not_sent: {
    text: "Not notified",
    className: "border-slate-200 bg-white text-slate-400",
  },
};

const how = (s) =>
  s.channel === "manual"
    ? " manually"
    : s.channel === "auto"
      ? " automatically"
      : " by email";

const describe = (step, s) => {
  if (s.state === "not_sent") return `${step.label}: not notified`;
  if (s.state === "failed") return `${step.label}: failed on ${s.at}`;
  if (s.state === "replied") return `${step.label}: replied ${s.at}`;
  return `${step.label}: notified${how(s)} ${s.at}`;
};

/**
 * EmailDots
 *
 * One line per notification of the round, in the order they go out: a badge
 * that says where it stands — Replied, Notified (with "manually" when it went
 * out some other way and was recorded as a note, which counts), Failed, or Not
 * notified — then its name and date. Lines not yet notified are greyed so the
 * ones that have gone stand out. Pressing a line opens the person's timeline.
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
}) => (
  <ul className="space-y-0.5">
    {stepsFor(registered).map((step) => {
      const s = stepState(step, person, emails, notes, notifications);
      const badge = BADGE[s.state];
      return (
        <li key={step.key}>
          <button
            type="button"
            aria-label={describe(step, s)}
            onClick={onOpen}
            className={`flex items-center gap-2 text-left text-xs ${
              s.state === "not_sent" ? "text-slate-400" : "text-slate-700"
            }`}
          >
            <Badge
              variant="outline"
              className={`w-24 shrink-0 justify-center px-1 py-0 text-[10px] ${badge.className}`}
            >
              {badge.text}
              {s.channel === "manual" ? " · manually" : ""}
            </Badge>
            <span className="whitespace-nowrap">
              {step.label}
              {s.at ? ` · ${s.at}` : ""}
            </span>
          </button>
        </li>
      );
    })}
  </ul>
);

export default EmailDots;
