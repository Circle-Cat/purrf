import { Badge } from "@/components/ui/badge";
// A `title` rather than a TermHint: this whole card is one <button>, so a
// tooltip trigger inside it would nest a control in a control and swallow the
// click the card exists to receive. Same copy, weaker affordance, forced by
// the structure.
import { termHint } from "@/pages/Recruiting/components/glossary";
import {
  humanize,
  INTERVIEW_STAGES,
} from "@/pages/Recruiting/board/stageFormat";
import { formatDateWithZone, resolveViewerTimezone } from "@/utils/dateTime";

/**
 * One applicant card on the board: applicant name, an optional sub-status
 * badge (pipeline lanes only), a reviewer line (interview-stage cards
 * only), tag chips (a live cold-freeze countdown shown only during the
 * cooldown window, plus blacklisted, when present), and the applied date.
 * The whole card is a button so any lane can open the detail view for it.
 *
 * The blacklist tag chip distinguishes two states: `tags.blacklisted` alone
 * just records that this application was once rejected by a blacklist
 * action (a historical fact that never changes); `isBlocked` reflects
 * whether the applicant is CURRENTLY blocked. A rejected application whose
 * applicant has since been unblocked shows "Blacklist Lifted" instead of
 * "Blacklisted", so the board doesn't look like it's flagging someone who
 * is no longer blocked.
 *
 * `highlighted` rings the card in blue; the board sets it on the applicant
 * an owner has just come back from, so it can be spotted without reading
 * every name in the lane.
 *
 * @param {{
 *   card: {id: number, applicantName: string, applicantEmail: string,
 *     stage: string, subStatus: string|null, tags: object|null,
 *     appliedAt: string|null, isBlocked: boolean, reviewerName: string|null},
 *   showStatus: boolean,
 *   highlighted?: boolean,
 *   onOpen: (id: number) => void,
 * }} props
 */

/**
 * Whole days from local midnight today until the given date-only string
 * ("YYYY-MM-DD"). Timezone-stable: compares calendar dates, not instants.
 * Returns 0 for a missing/unparseable date. Positive means the date is in
 * the future; 0 or negative means today or past.
 */
const daysUntil = (isoDate) => {
  if (!isoDate) return 0;
  const [y, m, d] = isoDate.split("-").map(Number);
  if (!y || !m || !d) return 0;
  const thaw = new Date(y, m - 1, d);
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  return Math.round((thaw - today) / 86400000);
};

const ApplicantCard = ({ card, showStatus, highlighted = false, onOpen }) => {
  const daysLeft = daysUntil(card.tags?.cold_freeze?.thaw_date);
  const showColdFreeze = daysLeft > 0;

  return (
    <button
      type="button"
      data-application-id={String(card.id)}
      onClick={() => onOpen(card.id)}
      className={`w-full space-y-2 rounded-lg border bg-white p-3 text-left shadow-sm transition-colors hover:bg-slate-50 ${
        highlighted
          ? "border-blue-500 ring-2 ring-blue-400"
          : "border-slate-200"
      }`}
    >
      <div className="flex items-center justify-between gap-2">
        <p className="font-medium text-slate-900">{card.applicantName}</p>
        {showStatus && card.subStatus && (
          <Badge variant="outline">{humanize(card.subStatus)}</Badge>
        )}
      </div>
      {INTERVIEW_STAGES.has(card.stage) && (
        <p
          className={
            card.reviewerName
              ? "text-sm font-medium text-blue-600"
              : "text-sm text-slate-400"
          }
        >
          Reviewer: {card.reviewerName ?? "N/A"}
        </p>
      )}
      {showColdFreeze || card.tags?.blacklisted ? (
        <div className="flex flex-wrap gap-1">
          {showColdFreeze && (
            <Badge variant="secondary" title={termHint("tag.cold_freeze")}>
              Cold freeze · {daysLeft} {daysLeft === 1 ? "day" : "days"} left
            </Badge>
          )}
          {card.tags?.blacklisted &&
            (card.isBlocked ? (
              <Badge variant="destructive" title={termHint("tag.blacklisted")}>
                Blacklisted
              </Badge>
            ) : (
              <Badge
                variant="secondary"
                title={termHint("tag.blacklist_lifted")}
              >
                Blacklist Lifted
              </Badge>
            ))}
        </div>
      ) : null}
      {card.appliedAt && (
        <p className="text-xs text-slate-500">
          {formatDateWithZone(card.appliedAt, resolveViewerTimezone())}
        </p>
      )}
    </button>
  );
};

export default ApplicantCard;
