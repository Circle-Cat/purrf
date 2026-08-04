import { Link } from "react-router-dom";
import { ArrowLeft } from "lucide-react";
import { ROUTE_PATHS } from "@/constants/RoutePaths";

/**
 * The application detail page's way back out, aimed at wherever the viewer
 * came from.
 *
 * Three outcomes, in order:
 * - In evaluate mode the viewer arrived from My Interview Evaluations, and may not own
 *   the posting at all, so that's where they go back to.
 * - A viewer with `canView` (an owner, or a `read.all` holder) goes back to
 *   the board, carrying the job so their selection survives and the
 *   application id as `focus` so the board scrolls to and rings that card.
 * - Anyone else — in practice a pure current-stage assignee who reached this
 *   page without `?mode=evaluate` — gets no link. The board is gated on
 *   owner-or-`read.all`, so a link would only strand them on "You don't own
 *   any postings."
 *
 * `jobId` comes from the detail payload's `application.jobId`, which is
 * present regardless of `canView` — deliberately not from the separate
 * `getJob` fetch, which only runs on the `canView` branch.
 *
 * @param {{
 *   jobId: number|null,
 *   applicationId: string|number,
 *   evaluatorMode: boolean,
 *   canView: boolean,
 * }} props
 */
const BackToBoardLink = ({ jobId, applicationId, evaluatorMode, canView }) => {
  const className =
    "inline-flex items-center gap-1 text-sm font-medium text-slate-600 hover:text-slate-900";

  if (evaluatorMode) {
    return (
      <Link to={ROUTE_PATHS.RECRUITING_MY_EVALUATIONS} className={className}>
        <ArrowLeft className="h-4 w-4" aria-hidden />
        My Interview Evaluations
      </Link>
    );
  }

  if (!canView || jobId == null) return null;

  return (
    <Link
      to={`${ROUTE_PATHS.RECRUITING_BOARD}?jobId=${jobId}&focus=${applicationId}`}
      className={className}
    >
      <ArrowLeft className="h-4 w-4" aria-hidden />
      Applications Board
    </Link>
  );
};

export default BackToBoardLink;
