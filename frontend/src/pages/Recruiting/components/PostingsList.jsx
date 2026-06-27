import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

/** Human labels + badge variants per JobStatus. */
const STATUS_LABELS = {
  draft: "Draft",
  pending_review: "Pending review",
  published: "Published",
  published_pending_revision: "Revision pending review",
  closed: "Closed",
};

const VARIANT = {
  draft: "secondary",
  pending_review: "outline",
  published: "default",
  published_pending_revision: "outline",
  closed: "secondary",
};

/**
 * Read-only table of postings with status-driven action buttons.
 *
 * @param {{jobs: object[], onEdit?: Function, onSubmit?: Function,
 *          onClose?: Function, onReopen?: Function, onView?: Function}} props
 */
const PostingsList = ({
  jobs,
  onEdit,
  onSubmit,
  onClose,
  onReopen,
  onView,
}) => (
  <div className="divide-y divide-slate-200 rounded-lg border border-slate-200 bg-white">
    {jobs.length === 0 && (
      <p className="p-6 text-sm text-slate-500">No postings yet.</p>
    )}
    {jobs.map((job) => {
      const canEdit = job.status === "draft" || job.status === "published";
      const canSubmit =
        job.status === "draft" || job.status === "published_pending_revision";
      const canClose =
        job.status === "draft" ||
        job.status === "published" ||
        job.status === "published_pending_revision";
      const canReopen = job.status === "closed";
      return (
        <div key={job.id} className="flex items-center gap-3 p-4">
          <div className="min-w-0 flex-1">
            <p className="truncate font-medium text-slate-900">{job.title}</p>
            <p className="text-xs text-slate-500">{job.kind}</p>
          </div>
          <Badge variant={VARIANT[job.status]}>
            {STATUS_LABELS[job.status]}
          </Badge>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" onClick={() => onView?.(job)}>
              View
            </Button>
            {canEdit && (
              <Button variant="outline" size="sm" onClick={() => onEdit?.(job)}>
                Edit
              </Button>
            )}
            {canSubmit && (
              <Button size="sm" onClick={() => onSubmit?.(job.id)}>
                Submit for review
              </Button>
            )}
            {canClose && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => onClose?.(job.id)}
              >
                Close
              </Button>
            )}
            {canReopen && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => onReopen?.(job.id)}
              >
                Reopen
              </Button>
            )}
          </div>
        </div>
      );
    })}
  </div>
);

export default PostingsList;
