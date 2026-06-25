import { useState } from "react";
import { ChevronRight } from "lucide-react";
import { reviewsForUser } from "@/pages/RecruitingPrototype/mockData";
import ReviewDetailPrototype from "@/pages/RecruitingPrototype/ReviewDetailPrototype";

/**
 * "待我审核" queue for one reviewer. Lists postings pending this reviewer's
 * decision (initial reviews and published-posting revision reviews) and opens
 * the read-only review detail on click. Approving / sending back closes the
 * detail and the queue shrinks as the shared postings state updates.
 *
 * @param {Object} props
 * @param {object[]} props.postings
 * @param {number} props.reviewerId
 * @param {(id:number) => void} props.onApprove
 * @param {(id:number, comment:string) => void} props.onSendBack
 * @returns {JSX.Element}
 */
const ReviewQueuePrototype = ({
  postings,
  reviewerId,
  onApprove,
  onSendBack,
}) => {
  const [openId, setOpenId] = useState(null);
  const queue = reviewsForUser(postings, reviewerId);
  const open = queue.find((p) => p.id === openId) ?? null;

  if (open) {
    return (
      <ReviewDetailPrototype
        posting={open}
        onBack={() => setOpenId(null)}
        onApprove={(id) => {
          onApprove(id);
          setOpenId(null);
        }}
        onSendBack={(id, c) => {
          onSendBack(id, c);
          setOpenId(null);
        }}
      />
    );
  }

  return (
    <div className="p-6">
      <h2 className="text-lg font-semibold text-slate-900 mb-4">待我审核</h2>
      {queue.length === 0 ? (
        <p className="text-sm text-slate-400">暂无待审职位。</p>
      ) : (
        <div className="space-y-2">
          {queue.map((p) => (
            <button
              key={p.id}
              type="button"
              onClick={() => setOpenId(p.id)}
              className="w-full flex items-center justify-between rounded-xl border border-slate-200 bg-white px-4 py-3 text-left hover:border-slate-400 transition-colors"
            >
              <div>
                <p className="text-sm font-medium text-slate-800">{p.title}</p>
                <p className="text-xs text-slate-400">
                  {p.kind}
                  {p.status === "published_pending_revision" && " · 改动重审"}
                </p>
              </div>
              <ChevronRight size={16} className="text-slate-400" />
            </button>
          ))}
        </div>
      )}
    </div>
  );
};

export default ReviewQueuePrototype;
