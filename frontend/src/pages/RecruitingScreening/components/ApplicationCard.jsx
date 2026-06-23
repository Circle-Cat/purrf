import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

/**
 * Formats a UTC ISO date string into a short human-readable date (e.g. "Jul 1, 2026").
 *
 * @param {string} isoString - An ISO 8601 date string.
 * @returns {string} Formatted date string.
 */
function formatDate(isoString) {
  return new Date(isoString).toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

/**
 * ApplicationCard
 *
 * Displays a single application board card for the screening view. Shows the
 * applicant identifier (userId), a view-state badge ("Unviewed (editable)" or
 * "Locked"), an optional freeze badge, and action buttons (Open, Hire, Reject).
 *
 * Open is gated on canRead; Hire/Reject are gated on canAdvance.
 *
 * @param {Object}        props
 * @param {Object}        props.card          - The ApplicationBoardCardDto.
 * @param {number}        props.card.id       - Application ID.
 * @param {number}        props.card.userId   - Applicant user ID.
 * @param {boolean}       props.card.isViewed - Whether the screener has opened it.
 * @param {string|null}   props.card.freezeUntil - ISO date until the card is frozen, or null.
 * @param {boolean}       props.canRead       - Whether the user may open the application.
 * @param {boolean}       props.canAdvance    - Whether the user may hire/reject.
 * @param {Function}      props.onOpen        - Called when Open is clicked.
 * @param {Function}      props.onHire        - Called when Hire is clicked.
 * @param {Function}      props.onReject      - Called when Reject is clicked.
 * @returns {JSX.Element}
 */
const ApplicationCard = ({
  card,
  canRead,
  canAdvance,
  onOpen,
  onHire,
  onReject,
}) => {
  const { id, userId, isViewed, freezeUntil } = card;

  return (
    <Card className="border-gray-200 shadow-sm">
      <CardContent className="pt-4 flex flex-col gap-2">
        {/* Applicant identifier */}
        <span className="font-medium text-sm">User {userId}</span>

        {/* View-state badge */}
        <div className="flex flex-wrap gap-2">
          {isViewed ? (
            <Badge variant="secondary">Locked</Badge>
          ) : (
            <Badge variant="outline">Unviewed (editable)</Badge>
          )}

          {/* Freeze badge — shown only when freezeUntil is set */}
          {freezeUntil && (
            <Badge variant="destructive">
              Frozen until {formatDate(freezeUntil)}
            </Badge>
          )}
        </div>

        {/* Action buttons */}
        <div className="flex gap-2 mt-1">
          {canRead && (
            <Button size="sm" variant="outline" onClick={() => onOpen(id)}>
              Open
            </Button>
          )}
          {canAdvance && (
            <>
              <Button size="sm" onClick={() => onHire(id)}>
                Hire
              </Button>
              <Button
                size="sm"
                variant="destructive"
                onClick={() => onReject(id)}
              >
                Reject
              </Button>
            </>
          )}
        </div>
      </CardContent>
    </Card>
  );
};

export default ApplicationCard;
