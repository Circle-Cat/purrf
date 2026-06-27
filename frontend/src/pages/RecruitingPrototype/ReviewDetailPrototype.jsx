import { useState } from "react";
import { ArrowLeft } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  STAGES,
  SAMPLE_FORM_SCHEMA,
} from "@/pages/RecruitingPrototype/mockData";
import JsonSchemaForm from "@/pages/RecruitingPrototype/vendor/JsonSchemaForm";

/** No-op for the read-only form preview (JsonSchemaForm is controlled). */
const noop = () => {};

/**
 * Read-only review of a posting: JD, the live application-form preview (reused
 * JsonSchemaForm, rendered non-interactive), and the pipeline. The reviewer can
 * approve, or send back with a mandatory comment. For a published posting's
 * revision, a banner flags the re-review and lists the changed fields.
 *
 * @param {Object} props
 * @param {object} props.posting
 * @param {() => void} props.onBack
 * @param {(id:number) => void} props.onApprove
 * @param {(id:number, comment:string) => void} props.onSendBack
 * @returns {JSX.Element}
 */
const ReviewDetailPrototype = ({ posting, onBack, onApprove, onSendBack }) => {
  const [rejecting, setRejecting] = useState(false);
  const [comment, setComment] = useState("");
  const isRevision = posting.status === "published_pending_revision";

  return (
    <div className="p-6 max-w-3xl">
      <button
        type="button"
        onClick={onBack}
        className="flex items-center gap-1 text-xs text-slate-500 hover:underline mb-3"
      >
        <ArrowLeft size={13} /> 返回队列
      </button>

      <h2 className="text-lg font-semibold text-slate-900">
        审核 · {posting.title}
        <span className="text-sm font-normal text-slate-400 ml-2">
          {posting.kind}
        </span>
      </h2>

      {isRevision && (
        <div className="mt-2 rounded-lg bg-orange-50 border border-orange-200 px-3 py-2 text-sm text-orange-800">
          本次为已发布职位的<strong>改动重审</strong> · 改动字段:
          {posting.pendingRevision?.changedFields.join("、")}
          <span className="block text-xs text-orange-600 mt-0.5">
            线上仍服务旧版本,批准后才切换。
          </span>
        </div>
      )}

      {posting.submitMessage && (
        <p className="mt-2 text-sm text-slate-500">
          提交留言:“{posting.submitMessage}”
        </p>
      )}

      <section className="mt-4">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-1">
          ① 职位描述
        </h3>
        <p className="text-sm text-slate-700 leading-relaxed">
          {posting.description}
        </p>
      </section>

      <section className="mt-4">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-1">
          ② 投递表单预览
        </h3>
        <div className="pointer-events-none select-none opacity-90 rounded-lg border border-slate-200 p-4">
          <JsonSchemaForm
            schema={SAMPLE_FORM_SCHEMA}
            value={{}}
            onChange={noop}
          />
        </div>
      </section>

      <section className="mt-4">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-1">
          ③ 面试流程
        </h3>
        <p className="text-sm text-slate-700">
          {posting.stages.length
            ? posting.stages.map((s) => STAGES[s]?.label ?? s).join(" → ")
            : "(无评审阶段,直接录取)"}
        </p>
      </section>

      <div className="mt-6">
        {rejecting ? (
          <div className="space-y-2">
            <textarea
              rows={3}
              placeholder="打回意见(必填)"
              value={comment}
              onChange={(e) => setComment(e.target.value)}
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring resize-y"
            />
            <div className="flex gap-2 justify-end">
              <Button variant="outline" onClick={() => setRejecting(false)}>
                取消
              </Button>
              <Button
                variant="destructive"
                disabled={!comment.trim()}
                onClick={() => onSendBack(posting.id, comment.trim())}
              >
                确认打回
              </Button>
            </div>
          </div>
        ) : (
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => setRejecting(true)}>
              打回
            </Button>
            <Button onClick={() => onApprove(posting.id)}>✓ 批准发布</Button>
          </div>
        )}
      </div>
    </div>
  );
};

export default ReviewDetailPrototype;
