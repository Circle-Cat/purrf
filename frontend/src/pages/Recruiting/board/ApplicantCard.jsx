import { Badge } from "@/components/ui/badge";

/**
 * One applicant card on the board: applicant name, an optional sub-status
 * badge (pipeline lanes only), tag chips (cold freeze / blacklisted, when
 * present), and the applied date. The whole card is a button so any lane
 * can open the detail view for it.
 *
 * @param {{
 *   card: {id: number, applicantName: string, applicantEmail: string,
 *     stage: string, subStatus: string|null, tags: object|null,
 *     appliedAt: string|null},
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
          <Badge variant="outline">{card.subStatus}</Badge>
        )}
      </div>
      {card.tags?.coldFreeze || card.tags?.blacklisted ? (
        <div className="flex flex-wrap gap-1">
          {card.tags?.coldFreeze && (
            <Badge variant="secondary">Cold freeze</Badge>
          )}
          {card.tags?.blacklisted && (
            <Badge variant="destructive">Blacklisted</Badge>
          )}
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
