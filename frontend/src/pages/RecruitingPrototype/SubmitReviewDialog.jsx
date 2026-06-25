import { useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { REVIEWERS } from "@/pages/RecruitingPrototype/mockData";

/**
 * Submit-for-review dialog. Lists eligible reviewers (job.approve holders,
 * excluding the current user so there is no self-review), enforces the
 * approver-pool floor (≥1 eligible reviewer ≠ submitter), and collects an
 * optional message. Submitting is disabled until a reviewer is picked.
 *
 * @param {Object} props
 * @param {object|null} props.posting - Posting being submitted; null = closed (renders nothing).
 * @param {number} props.currentUserId - The submitter, excluded from the reviewer list.
 * @param {() => void} props.onClose
 * @param {(id:number, reviewerId:number, msg:string) => void} props.onSubmit
 * @returns {JSX.Element|null}
 */
const SubmitReviewDialog = ({ posting, currentUserId, onClose, onSubmit }) => {
  const [reviewerId, setReviewerId] = useState(null);
  const [message, setMessage] = useState("");

  if (!posting) return null;

  const eligible = REVIEWERS.filter((r) => r.id !== currentUserId);
  const poolTooSmall = eligible.length < 1;

  const submit = () => {
    if (reviewerId == null) return;
    onSubmit(posting.id, reviewerId, message.trim());
    onClose();
  };

  return (
    <Dialog open={!!posting} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>提交审核 · {posting.title}</DialogTitle>
        </DialogHeader>

        {poolTooSmall ? (
          <p className="text-sm text-rose-600 py-4">
            审核人池不足,无法提交(需至少一名非本人的 job.approve 持有者)。
          </p>
        ) : (
          <>
            <div className="space-y-1.5">
              <p className="text-xs font-medium text-slate-500">
                选择审核人(不含你自己)
              </p>
              {eligible.map((r) => (
                <label
                  key={r.id}
                  className="flex items-center gap-2 text-sm text-slate-700 cursor-pointer"
                >
                  <input
                    type="radio"
                    name="reviewer"
                    checked={reviewerId === r.id}
                    onChange={() => setReviewerId(r.id)}
                  />
                  {r.name}{" "}
                  <span className="text-slate-400 text-xs">{r.email}</span>
                </label>
              ))}
            </div>
            <div className="mt-3 space-y-1.5">
              <p className="text-xs font-medium text-slate-500">
                留言给审核人(选填)
              </p>
              <textarea
                rows={3}
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring resize-y"
              />
            </div>
          </>
        )}

        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            取消
          </Button>
          <Button
            disabled={poolTooSmall || reviewerId == null}
            onClick={submit}
          >
            提交审核
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export default SubmitReviewDialog;
