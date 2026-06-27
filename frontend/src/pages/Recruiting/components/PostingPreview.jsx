import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

/** Pretty-printed read-only JSON block, or an em dash when empty. */
const Json = ({ value }) => (
  <pre className="max-h-64 overflow-auto rounded-md bg-slate-50 p-3 text-xs">
    {value ? JSON.stringify(value, null, 2) : "—"}
  </pre>
);

/**
 * Read-only preview Dialog for a job posting, available for any status.
 *
 * @param {{ open: boolean, job: object|null, onOpenChange: Function }} props
 */
const PostingPreview = ({ open, job, onOpenChange }) => (
  <Dialog open={open} onOpenChange={onOpenChange}>
    <DialogContent showCloseButton={false}>
      {job && (
        <>
          <DialogHeader>
            <DialogTitle>{job.title}</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            {job.lastRejectComment && (
              <div className="space-y-1">
                <p className="text-sm font-medium text-slate-700">
                  Rejection comment
                </p>
                <p className="text-sm text-red-600">{job.lastRejectComment}</p>
              </div>
            )}
            <p className="text-sm text-slate-600">{job.kind}</p>
            {job.description && (
              <p className="text-sm text-slate-700">{job.description}</p>
            )}
            <div className="space-y-1">
              <p className="text-sm font-medium text-slate-700">Pipeline</p>
              <Json value={job.pipelineConfig} />
            </div>
            <div className="space-y-1">
              <p className="text-sm font-medium text-slate-700">Form schema</p>
              {job.status === "published_pending_revision" ? (
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <p className="text-xs text-slate-500">Live</p>
                    <Json value={job.formSchema} />
                  </div>
                  <div>
                    <p className="text-xs text-slate-500">Pending revision</p>
                    <Json value={job.pendingFormSchema} />
                  </div>
                </div>
              ) : (
                <Json value={job.formSchema} />
              )}
            </div>
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
