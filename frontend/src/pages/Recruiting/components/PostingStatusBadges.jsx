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

const STATUS_VARIANT = {
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
 * Status badge, plus a reject-reason badge (with popover detail) when the
 * posting's most recent review was a rejection. Shared between
 * PostingsList and PostingDetailPage.
 *
 * @param {{job: {status: string, lastRejectComment?: string,
 *          lastRejectKind?: string}, onRejectBadgeClick?: (e: Event) => void}} props
 */
const PostingStatusBadges = ({ job, onRejectBadgeClick = () => {} }) => (
  <>
    <Badge variant={STATUS_VARIANT[job.status]}>
      {STATUS_LABELS[job.status]}
    </Badge>
    {job.lastRejectComment && (
      <Popover>
        <PopoverTrigger asChild>
          <span
            role="button"
            tabIndex={0}
            className="cursor-pointer"
            onClick={onRejectBadgeClick}
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
          <p className="text-sm text-red-600">{job.lastRejectComment}</p>
        </PopoverContent>
      </Popover>
    )}
  </>
);

export default PostingStatusBadges;
