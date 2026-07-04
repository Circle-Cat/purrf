import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";

/** Human labels + badge variants per JobStatus. */
const STATUS_LABELS = {
  draft: "Draft",
  pending_review: "Pending review",
  published: "Published",
  published_pending_revision: "Revision pending review",
  pending_close: "Pending close",
  pending_reopen: "Pending reopen",
  closed: "Closed",
};

const VARIANT = {
  draft: "secondary",
  pending_review: "outline",
  published: "default",
  published_pending_revision: "outline",
  pending_close: "outline",
  pending_reopen: "outline",
  closed: "secondary",
};

/**
 * Read-only table of postings with status-driven action buttons.
 *
 * Action matrix:
 * - draft: Edit, Submit for review, Close, View
 * - published: Edit, Request close, View
 * - published_pending_revision: Submit for review, View
 * - pending_review / pending_close / pending_reopen: View only
 * - closed + wasPublished: Edit, Request reopen, View
 * - closed (never published): Delete, View
 *
 * @param {{jobs: object[], approversById?: Record<number, string>,
 *          closingId?: number|null, onEdit?: Function, onSubmit?: Function,
 *          onClose?: Function, onRequestClose?: Function,
 *          onRequestReopen?: Function, onDelete?: Function,
 *          onView?: Function}} props
 */
const PostingsList = ({
  jobs,
  approversById = {},
  closingId = null,
  onEdit,
  onSubmit,
  onClose,
  onRequestClose,
  onRequestReopen,
  onDelete,
  onView,
}) => (
  <div className="divide-y divide-slate-200 rounded-lg border border-slate-200 bg-white">
    {jobs.length === 0 && (
      <p className="p-6 text-sm text-slate-500">No postings yet.</p>
    )}
    {jobs.map((job) => {
      const isDraft = job.status === "draft";
      const isPublished = job.status === "published";
      const isPendingRevision = job.status === "published_pending_revision";
      const isClosed = job.status === "closed";
      const reviewerName = job.reviewerId
        ? (approversById[job.reviewerId] ?? `Reviewer #${job.reviewerId}`)
        : null;

      return (
        <div key={job.id} className="flex items-center gap-3 p-4">
          <div className="min-w-0 flex-1">
            <p className="truncate font-medium text-slate-900">{job.title}</p>
            <p className="text-xs text-slate-500">{job.kind}</p>
          </div>
          <div className="flex flex-col items-end gap-1">
            {isDraft && job.lastRejectComment ? (
              <Popover>
                <PopoverTrigger asChild>
                  <button type="button" className="cursor-pointer">
                    <Badge variant="destructive">Sent back</Badge>
                  </button>
                </PopoverTrigger>
                <PopoverContent className="w-72">
                  <p className="text-sm font-medium text-slate-700">
                    Rejection comment
                  </p>
                  <p className="text-sm text-red-600">
                    {job.lastRejectComment}
                  </p>
                </PopoverContent>
              </Popover>
            ) : (
              <Badge variant={VARIANT[job.status]}>
                {STATUS_LABELS[job.status]}
              </Badge>
            )}
            {reviewerName && (
              <p className="text-xs text-slate-500">
                Assigned to: {reviewerName}
              </p>
            )}
          </div>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" onClick={() => onView?.(job)}>
              View
            </Button>
            {isDraft && (
              <>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => onEdit?.(job)}
                >
                  Edit
                </Button>
                <Button size="sm" onClick={() => onSubmit?.(job.id)}>
                  Submit for review
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={closingId === job.id}
                  onClick={() => onClose?.(job.id)}
                >
                  Close
                </Button>
              </>
            )}
            {isPublished && (
              <>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => onEdit?.(job)}
                >
                  Edit
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => onRequestClose?.(job.id)}
                >
                  Request close
                </Button>
              </>
            )}
            {isPendingRevision && (
              <Button size="sm" onClick={() => onSubmit?.(job.id)}>
                Submit for review
              </Button>
            )}
            {isClosed && job.wasPublished && (
              <>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => onEdit?.(job)}
                >
                  Edit
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => onRequestReopen?.(job.id)}
                >
                  Request reopen
                </Button>
              </>
            )}
            {isClosed && !job.wasPublished && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => onDelete?.(job.id)}
              >
                Delete
              </Button>
            )}
          </div>
        </div>
      );
    })}
  </div>
);

export default PostingsList;
