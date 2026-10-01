import { Fragment } from "react";
import PostingStatusBadges from "@/pages/Recruiting/components/PostingStatusBadges";
import { unavailablePersonLabel } from "@/pages/Recruiting/components/personLabel";

/**
 * Read-only, browse-only table of postings — status Badge, "Recruiter"
 * line, and a click-through to the unified job detail page. All lifecycle
 * actions (Edit/Submit/Delete/Request close/Request reopen) live on that
 * detail page now, not here, so this list is safe to show to
 * `RECRUITING_JOB_READ`-only viewers too. It draws no frame of its own:
 * it sits inside the page's Postings card.
 *
 * @param {{jobs: object[], ownersById?: Record<number, string>,
 *          onRowClick: (job: object) => void}} props
 */
const PostingsList = ({ jobs, ownersById = {}, onRowClick }) => (
  <div className="divide-y divide-slate-200">
    {jobs.length === 0 && (
      <p className="px-5 py-4 text-sm text-slate-500">No postings yet.</p>
    )}
    {jobs.map((job) => {
      const ownerIds = job.pipelineConfig?.ownerIds ?? [];

      return (
        <button
          key={job.id}
          type="button"
          className="flex w-full items-center gap-3 px-5 py-4 text-left last:rounded-b-lg hover:bg-slate-50"
          onClick={() => onRowClick(job)}
        >
          <div className="min-w-0 flex-1">
            <p className="truncate font-medium text-slate-900">{job.title}</p>
            <p className="text-xs text-slate-500">{job.kind}</p>
            {ownerIds.length > 0 && (
              <p className="text-xs text-slate-500">
                Recruiter:
                {ownerIds.map((oid, i) => (
                  <Fragment key={oid}>
                    {i === 0 ? " " : ", "}
                    {ownersById[oid] == null ? (
                      <span className="text-red-600">
                        {unavailablePersonLabel(oid)}
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
            <PostingStatusBadges job={job} />
          </div>
        </button>
      );
    })}
  </div>
);

export default PostingsList;
