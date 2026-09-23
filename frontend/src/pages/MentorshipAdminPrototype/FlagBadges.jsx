import { Badge } from "@/components/ui/badge";
import { NOTE_LABELS } from "@/pages/MentorshipAdminPrototype/mockData";

/**
 * FlagBadges
 *
 * The judgement flags that still stand on a person — no show, red flag,
 * partner change — beside their status rather than instead of it: a flag does
 * not end a status, so "matched" and "no show ×2" are both true at once.
 * Revoked flags are not counted; they stay on the timeline, struck through.
 *
 * @param {{flags: Record<string, number>}} props
 * @returns {JSX.Element|null}
 */
const FlagBadges = ({ flags }) => {
  const entries = Object.entries(flags ?? {});
  if (entries.length === 0) return null;
  return (
    <span className="ml-1 inline-flex flex-wrap gap-1">
      {entries.map(([tag, count]) => (
        <Badge key={tag} variant="destructive">
          {NOTE_LABELS[tag]}
          {count > 1 ? ` ×${count}` : ""}
        </Badge>
      ))}
    </span>
  );
};

export default FlagBadges;
