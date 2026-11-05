import { Badge } from "@/components/ui/badge";

const MARK_CLASS = "border-red-300 bg-red-50 text-red-800";

const counted = (label, count) => (count > 1 ? `${label} ×${count}` : label);

/**
 * The no show and red flag marks someone got in a round: one badge per kind,
 * with the count when there is more than one. Nothing when there are none.
 * Admin views only; participants never see their marks.
 *
 * @param {{noShow?: number, redFlag?: number}} props
 * @returns {JSX.Element|null}
 */
const MarkBadges = ({ noShow = 0, redFlag = 0 }) => {
  if (!noShow && !redFlag) return null;
  return (
    <span className="inline-flex flex-wrap items-center gap-1">
      {noShow > 0 && (
        <Badge variant="outline" className={MARK_CLASS}>
          {counted("No show", noShow)}
        </Badge>
      )}
      {redFlag > 0 && (
        <Badge variant="outline" className={MARK_CLASS}>
          {counted("Red flag", redFlag)}
        </Badge>
      )}
    </span>
  );
};

export default MarkBadges;
