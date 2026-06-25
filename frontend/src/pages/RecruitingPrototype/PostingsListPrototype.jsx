import { useState } from "react";
import { Plus, ArrowLeft } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import JobModalPrototype from "@/pages/RecruitingPrototype/JobModalPrototype";
import SubmitReviewDialog from "@/pages/RecruitingPrototype/SubmitReviewDialog";
import {
  POSTING_STATUS,
  reviewerName,
} from "@/pages/RecruitingPrototype/mockData";

/**
 * Per-status action labels. Only "提交审核" (→ submit dialog) and the create/
 * edit entry are wired; the rest are mock affordances (close/reopen/view), in
 * line with the breadth-first, no-strong-linkage prototype scope.
 */
const ACTIONS = {
  draft: ["编辑", "提交审核"],
  pending_review: ["查看"],
  published: ["查看", "关闭", "编辑"],
  closed: ["查看", "重开"],
  published_pending_revision: ["查看线上", "查看 diff"],
};

/**
 * Postings list — the submitter's home. Shows every posting with a status badge
 * and status-dependent actions; "新建职位" opens the JobModal inline. A draft
 * that was sent back shows the reviewer's rejection comment as a banner. A
 * pending-revision posting shows its live-vs-pending dual-version block.
 *
 * @param {Object} props
 * @param {object[]} props.postings
 * @param {number} props.currentUserId
 * @param {(id:number, reviewerId:number, msg:string)=>void} props.onSubmitForReview
 * @param {(job:object)=>void} props.onCreate
 * @returns {JSX.Element}
 */
const PostingsListPrototype = ({
  postings,
  currentUserId,
  onSubmitForReview,
  onCreate,
}) => {
  const [creating, setCreating] = useState(false);
  const [submitting, setSubmitting] = useState(null);

  if (creating) {
    return (
      <div className="p-6">
        <button
          type="button"
          onClick={() => setCreating(false)}
          className="flex items-center gap-1 text-xs text-slate-500 hover:underline mb-3"
        >
          <ArrowLeft size={13} /> 返回 Postings
        </button>
        <JobModalPrototype
          initialJob={null}
          onSave={onCreate}
          onClose={() => setCreating(false)}
        />
      </div>
    );
  }

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold text-slate-900">Postings</h2>
        <Button size="sm" onClick={() => setCreating(true)}>
          <Plus size={15} className="mr-1" /> 新建职位
        </Button>
      </div>

      <div className="space-y-2">
        {postings.map((p) => {
          const st = POSTING_STATUS[p.status];
          return (
            <div
              key={p.id}
              className="rounded-xl border border-slate-200 bg-white px-4 py-3"
            >
              {p.status === "draft" && p.rejectComment && (
                <div className="mb-2 rounded-lg bg-amber-50 border border-amber-200 px-3 py-2 text-xs text-amber-800">
                  ⚠ 已被 {reviewerName(p.rejectedBy)} 打回 — {p.rejectComment}
                  <span className="text-amber-600">
                    {" "}
                    · 改完后可重新提交审核
                  </span>
                </div>
              )}

              <div className="flex items-center justify-between gap-3">
                <div className="min-w-0">
                  <p className="text-sm font-medium text-slate-800 truncate">
                    {p.title}
                  </p>
                  <p className="text-xs text-slate-400">{p.kind}</p>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  <Badge variant="outline" className={`text-xs ${st.badge}`}>
                    {st.label}
                  </Badge>
                  {p.status === "pending_review" && (
                    <span className="text-xs text-slate-400">
                      → {reviewerName(p.reviewerId)}
                    </span>
                  )}
                  {(ACTIONS[p.status] ?? []).map((a) => (
                    <button
                      key={a}
                      type="button"
                      onClick={
                        a === "提交审核" ? () => setSubmitting(p) : undefined
                      }
                      className="text-xs text-sky-600 hover:text-sky-700 hover:underline"
                    >
                      {a}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          );
        })}
      </div>

      <SubmitReviewDialog
        posting={submitting}
        currentUserId={currentUserId}
        onClose={() => setSubmitting(null)}
        onSubmit={onSubmitForReview}
      />
    </div>
  );
};

export default PostingsListPrototype;
