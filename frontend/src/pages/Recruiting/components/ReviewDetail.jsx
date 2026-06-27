import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";

/** Pretty-printed read-only JSON block, or an em dash when empty. */
const Json = ({ value }) => (
  <pre className="max-h-64 overflow-auto rounded-md bg-slate-50 p-3 text-xs">
    {value ? JSON.stringify(value, null, 2) : "—"}
  </pre>
);

/**
 * Reviewer's read-only view of a posting under review, with approve/reject.
 *
 * @param {{review: object, job: object, onApprove: Function,
 *          onReject: Function, onBack: Function}} props
 */
const ReviewDetail = ({ review, job, onApprove, onReject, onBack }) => {
  const [comment, setComment] = useState("");
  const isRevision = review.kind === "revision";

  return (
    <div className="space-y-4 p-6">
      <Button variant="outline" size="sm" onClick={onBack}>← Back</Button>
      <div>
        <h1 className="text-xl font-semibold text-slate-900">{job.title}</h1>
        <p className="text-sm text-slate-600">{job.description}</p>
      </div>
      {review.submitMessage && (
        <p className="rounded-md bg-blue-50 p-3 text-sm text-slate-700">
          {review.submitMessage}
        </p>
      )}
      <div className="space-y-1">
        <p className="text-sm font-medium text-slate-700">Pipeline</p>
        <Json value={job.pipelineConfig} />
      </div>
      <div className="space-y-1">
        <p className="text-sm font-medium text-slate-700">Form schema</p>
        {isRevision ? (
          <div className="grid grid-cols-2 gap-3">
            <div>
              <p className="text-xs text-slate-500">Live</p>
              <Json value={job.formSchema} />
            </div>
            <div>
              <p className="text-xs text-slate-500">Pending</p>
              <Json value={job.pendingFormSchema} />
            </div>
          </div>
        ) : (
          <Json value={job.formSchema} />
        )}
      </div>
      <div className="space-y-2 border-t border-slate-200 pt-4">
        <div className="space-y-1">
          <Label htmlFor="comment">Rejection comment</Label>
          <Textarea
            id="comment"
            rows={2}
            value={comment}
            onChange={(e) => setComment(e.target.value)}
          />
        </div>
        <div className="flex gap-2">
          <Button onClick={onApprove}>Approve</Button>
          <Button
            variant="destructive"
            disabled={!comment.trim()}
            onClick={() => onReject(comment.trim())}
          >
            Reject
          </Button>
        </div>
      </div>
    </div>
  );
};

export default ReviewDetail;
