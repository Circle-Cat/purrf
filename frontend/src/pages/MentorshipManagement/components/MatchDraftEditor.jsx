import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { personWithId } from "@/pages/MentorshipManagement/utils/matchingLabels";
import {
  NO_MENTOR,
  REASON_LIMIT,
  differsFromMatcher,
  mentorChoices,
  mentorOptionLabel,
} from "@/pages/MentorshipManagement/utils/matchDraft";

/**
 * What the matcher proposed for a mentee, shown once the row's mentor or
 * reason no longer is that; with `onRevert` it offers to go back to it.
 *
 * @param {{item: Object, shown: {mentorId: string|null,
 *          recommendationReason: string}, onRevert?: () => void}} props
 */
export const MatcherProposal = ({ item, shown, onRevert }) => {
  if (!differsFromMatcher(shown, item)) return null;
  const mentor = item.matcherMentor
    ? personWithId(item.matcherMentor)
    : "No mentor";
  return (
    <div className="space-y-2 rounded-md border border-border bg-background p-3">
      <p>
        The matcher proposed: {mentor} — {item.matcherReason || "no reason"}
      </p>
      {onRevert ? (
        <Button variant="outline" size="sm" onClick={onRevert}>
          Revert to the matcher&apos;s result
        </Button>
      ) : null}
    </div>
  );
};

/**
 * The mentor select and the reason for one mentee, in edit mode. Choosing
 * another mentor clears the reason.
 *
 * @param {{item: Object, shown: {mentorId: string|null,
 *          recommendationReason: string},
 *          slots: Map<string, {slots: number, assigned: number}>,
 *          onChange: (next: {mentorId: string|null,
 *            recommendationReason: string}) => void}} props
 */
export const MenteeEditor = ({ item, shown, slots, onChange }) => {
  const reason = shown.recommendationReason;
  const tooLong = reason.length > REASON_LIMIT;
  return (
    <div className="space-y-3">
      <div className="space-y-1">
        <div className="font-semibold">Mentor</div>
        <Select
          value={shown.mentorId ?? NO_MENTOR}
          onValueChange={(value) =>
            onChange({
              mentorId: value === NO_MENTOR ? null : value,
              recommendationReason: "",
            })
          }
        >
          <SelectTrigger aria-label="Mentor" className="w-full bg-background">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={NO_MENTOR}>No mentor this round</SelectItem>
            {mentorChoices(item).map((choice) => (
              <SelectItem key={choice.userId} value={choice.userId}>
                {mentorOptionLabel(choice, slots.get(choice.userId))}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
      <div className="space-y-1">
        <div className="font-semibold">Reason shown to the pair</div>
        <Textarea
          aria-label="Reason shown to the pair"
          className="bg-background"
          value={reason}
          onChange={(e) =>
            onChange({
              mentorId: shown.mentorId,
              recommendationReason: e.target.value,
            })
          }
        />
        <div
          className={`text-right text-xs tabular-nums ${tooLong ? "text-red-600" : "text-muted-foreground"}`}
        >
          {reason.length}/{REASON_LIMIT}
        </div>
        {shown.mentorId && !reason.trim() ? (
          <p className="text-xs text-red-600">
            A matched mentee needs a reason.
          </p>
        ) : null}
      </div>
    </div>
  );
};
