import { Button } from "@/components/ui/button";
import PostingReviewView from "@/pages/Recruiting/components/PostingReviewView";

/**
 * Full-page, read-only preview of a posting (any status): a Back control plus the
 * shared applicant-facing view + pipeline. Mirrors the full-page chrome of the
 * reviewer's ReviewDetail, without the approve/reject actions.
 *
 * @param {{job: object, onBack: () => void}} props
 */
const PostingPreviewPage = ({ job, onBack }) => (
  <div className="space-y-4 p-6">
    <Button variant="outline" size="sm" onClick={onBack}>
      ← Back
    </Button>
    <PostingReviewView
      job={job}
      isRevision={job.status === "published_pending_revision"}
    />
  </div>
);

export default PostingPreviewPage;
