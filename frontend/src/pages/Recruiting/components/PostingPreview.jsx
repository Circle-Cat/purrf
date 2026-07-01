import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import PostingReviewView from "@/pages/Recruiting/components/PostingReviewView";

/**
 * Read-only preview Dialog for a job posting, available for any status. Renders
 * the shared applicant-facing view (plus pipeline), with a Pending|Live toggle
 * when the posting has a pending revision.
 *
 * @param {{ open: boolean, job: object|null, onOpenChange: Function }} props
 */
const PostingPreview = ({ open, job, onOpenChange }) => (
  <Dialog open={open} onOpenChange={onOpenChange}>
    <DialogContent showCloseButton={false}>
      {job && (
        <>
          <DialogHeader>
            <DialogTitle>Posting preview</DialogTitle>
          </DialogHeader>
          <div className="max-h-[70vh] overflow-y-auto">
            <PostingReviewView
              job={job}
              isRevision={job.status === "published_pending_revision"}
            />
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => onOpenChange(false)}>
              Close
            </Button>
          </DialogFooter>
        </>
      )}
    </DialogContent>
  </Dialog>
);

export default PostingPreview;
