import { Badge } from "@/components/ui/badge";
import {
  humanize,
  INTERVIEW_STAGES,
} from "@/pages/Recruiting/board/stageFormat";

/**
 * One applicant card on the board: applicant name, an optional sub-status
 * badge (pipeline lanes only), a reviewer line (interview-stage cards
 * only), tag chips (cold freeze / blacklisted, when present), and the
 * applied date. The whole card is a button so any lane can open the detail
 * view for it.
 *
 * The blacklist tag chip distinguishes two states: `tags.blacklisted` alone
 * just records that this application was once rejected by a blacklist
 * action (a historical fact that never changes); `isBlocked` reflects
 * whether the applicant is CURRENTLY blocked. A rejected application whose
 * applicant has since been unblocked shows "Blacklist Lifted" instead of
 * "Blacklisted", so the board doesn't look like it's flagging someone who
 * is no longer blocked.
 *
 * @param {{
 *   card: {id: number, applicantName: string, applicantEmail: string,
 *     stage: string, subStatus: string|null, tags: object|null,
 *     appliedAt: string|null, isBlocked: boolean, reviewerName: string|null},
 *   showStatus: boolean,
 *   onOpen: (id: number) => void,
 * }} props
 */
const ApplicantCard = ({ card, showStatus, onOpen }) => {
  return (
    <button
      type="button"
      onClick={() => onOpen(card.id)}
      className="w-full space-y-2 rounded-lg border border-slate-200 bg-white p-3 text-left shadow-sm transition-colors hover:bg-slate-50"
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
      {card.tags?.coldFreeze || card.tags?.blacklisted ? (
        <div className="flex flex-wrap gap-1">
          {card.tags?.coldFreeze && (
            <Badge variant="secondary">Cold freeze</Badge>
          )}
          {card.tags?.blacklisted &&
            (card.isBlocked ? (
              <Badge variant="destructive">Blacklisted</Badge>
            ) : (
              <Badge variant="secondary">Blacklist Lifted</Badge>
            ))}
        </div>
      ) : null}
      {card.appliedAt && (
        <p className="text-xs text-slate-500">
          {new Date(card.appliedAt).toLocaleDateString()}
        </p>
      )}
    </button>
  );
};

export default ApplicantCard;
