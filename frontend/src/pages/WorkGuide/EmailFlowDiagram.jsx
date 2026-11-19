import { ArrowDown, Mail } from "lucide-react";

const CASES = [
  {
    when: "A reply to an email sent from a page",
    lands: "Application: Emails tab / Participant page: Timeline",
  },
  {
    when: "A new email to mentorship@, recruiting@ or contact@",
    lands: "Inbox: Mentorship, Recruiting or Contact",
  },
  {
    when: "A new email sent straight to purrf@",
    lands: "Inbox: Unsorted",
  },
  {
    when: "A reply to a Kit or bell notification",
    lands: "Not collected in Purrf",
    warning: true,
  },
];

/**
 * Where incoming email lands: one shared mailbox fanning out to the four
 * places a message can end up.
 *
 * @returns {JSX.Element}
 */
const EmailFlowDiagram = () => (
  <figure className="flex flex-col items-center gap-3 rounded-xl border bg-muted/30 p-4 sm:p-6">
    <div className="flex items-center gap-2 rounded-lg border border-primary/30 bg-primary/5 px-4 py-2 text-sm font-semibold">
      <Mail className="size-4 text-primary" aria-hidden="true" />
      An email arrives at the shared mailbox
    </div>
    <ArrowDown className="size-4 text-muted-foreground" aria-hidden="true" />
    <ul className="grid w-full gap-3 sm:grid-cols-2">
      {CASES.map((c) => (
        <li
          key={c.lands}
          className={`flex flex-col gap-1 rounded-lg border p-3 text-sm ${
            c.warning
              ? "border-amber-300 bg-amber-50 dark:border-amber-700 dark:bg-amber-950/40"
              : "bg-background"
          }`}
        >
          <span className="text-muted-foreground">{c.when}</span>
          <span
            className={`font-semibold ${
              c.warning ? "text-amber-800 dark:text-amber-300" : ""
            }`}
          >
            {c.lands}
          </span>
        </li>
      ))}
    </ul>
    <figcaption className="sr-only">Where incoming email lands</figcaption>
  </figure>
);

export default EmailFlowDiagram;
