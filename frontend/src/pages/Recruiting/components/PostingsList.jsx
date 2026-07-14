import { Badge } from "@/components/ui/badge";
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

const REJECT_KIND_LABEL = {
  initial: "Initial submission rejected",
  revision: "Revision rejected",
  close: "Close request rejected",
  reopen: "Reopen request rejected",
};

/**
 * Read-only, browse-only table of postings — status Badge, "Managed by"
 * line, and a click-through to the unified job detail page. All lifecycle
 * actions (Edit/Submit/Delete/Request close/Request reopen) live on that
 * detail page now, not here, so this list is safe to show to
 * `RECRUITING_JOB_READ`-only viewers too.
 *
 * @param {{jobs: object[], ownersById?: Record<number, string>,
 *          onRowClick: (job: object) => void}} props
 */
const PostingsList = ({ jobs, ownersById = {}, onRowClick }) => (
  <div className="divide-y divide-slate-200 rounded-lg border border-slate-200 bg-white">
    {jobs.length === 0 && (
      <p className="p-6 text-sm text-slate-500">No postings yet.</p>
    )}
    {jobs.map((job) => {
      const ownerNames = (job.pipelineConfig?.ownerIds ?? [])
        .map((id) => ownersById[id] ?? `User ${id}`)
        .join(", ");

      return (
        <button
          key={job.id}
          type="button"
          className="flex w-full items-center gap-3 p-4 text-left hover:bg-slate-50"
          onClick={() => onRowClick(job)}
        >
          <div className="min-w-0 flex-1">
            <p className="truncate font-medium text-slate-900">{job.title}</p>
            <p className="text-xs text-slate-500">{job.kind}</p>
            {ownerNames && (
              <p className="text-xs text-slate-500">Managed by: {ownerNames}</p>
            )}
          </div>
          <div className="flex flex-col items-end gap-1">
            <Badge variant={VARIANT[job.status]}>
              {STATUS_LABELS[job.status]}
            </Badge>
            {job.lastRejectComment && (
              <Popover>
                <PopoverTrigger asChild>
                  <span
                    role="button"
                    tabIndex={0}
                    className="cursor-pointer"
                    onClick={(e) => e.stopPropagation()}
                  >
                    <Badge variant="destructive">
                      {REJECT_KIND_LABEL[job.lastRejectKind] ?? "Sent back"}
                    </Badge>
                  </span>
                </PopoverTrigger>
                <PopoverContent className="w-72">
                  <p className="text-sm font-medium text-slate-700">
                    {REJECT_KIND_LABEL[job.lastRejectKind] ?? "Rejected"}
                  </p>
                  <p className="text-sm text-red-600">
                    {job.lastRejectComment}
                  </p>
                </PopoverContent>
              </Popover>
            )}
          </div>
        </button>
      );
    })}
  </div>
);

export default PostingsList;
