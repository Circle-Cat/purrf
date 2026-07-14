import { Fragment } from "react";
import PostingStatusBadges from "@/pages/Recruiting/components/PostingStatusBadges";

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
      const ownerIds = job.pipelineConfig?.ownerIds ?? [];

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
            {ownerIds.length > 0 && (
              <p className="text-xs text-slate-500">
                Managed by:
                {ownerIds.map((oid, i) => (
                  <Fragment key={oid}>
                    {i === 0 ? " " : ", "}
                    {ownersById[oid] == null ? (
                      <span className="text-red-600">
                        {`#${oid} — no permission, remove`}
                      </span>
                    ) : (
                      ownersById[oid]
                    )}
                  </Fragment>
                ))}
              </p>
            )}
          </div>
          <div className="flex flex-col items-end gap-1">
            <PostingStatusBadges
              job={job}
              onRejectBadgeClick={(e) => e.stopPropagation()}
            />
          </div>
        </button>
      );
    })}
  </div>
);

export default PostingsList;
