import { useCallback, useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { getJob, createJob, updateJob } from "@/api/recruitingApi";
import { ROUTE_PATHS } from "@/constants/RoutePaths";
import JobBasicsSection from "@/pages/Recruiting/postings/JobBasicsSection";
import FormBuilder from "@/pages/Recruiting/postings/FormBuilder";
import FormRenderer from "@/pages/Recruiting/postings/FormRenderer";

/** A blank posting draft. */
const BLANK = {
  title: "",
  description: "",
  kind: "activity",
  formSchema: { questions: [] },
  pipelineConfig: null,
  screenRules: null,
  profileConfig: null,
};

/**
 * Build the create/update request body from a draft. Config sections not
 * edited in PR1 (pipeline/screen-rules/profile) pass through as loaded.
 *
 * @param {object} draft
 * @returns {object}
 */
const toBody = (draft) => ({
  title: draft.title,
  description: draft.description,
  kind: draft.kind,
  formSchema: draft.formSchema,
  pipelineConfig: draft.pipelineConfig ?? undefined,
  screenRules: draft.screenRules ?? undefined,
  profileConfig: draft.profileConfig ?? undefined,
});

/** Full-page create/edit posting screen. */
const PostingEditor = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const [draft, setDraft] = useState(BLANK);
  const [previewAnswers, setPreviewAnswers] = useState({});
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!id) return;
    getJob(id)
      .then(({ data }) =>
        setDraft({
          title: data.title ?? "",
          description: data.description ?? "",
          kind: data.kind ?? "activity",
          formSchema: data.formSchema ?? { questions: [] },
          pipelineConfig: data.pipelineConfig ?? null,
          screenRules: data.screenRules ?? null,
          profileConfig: data.profileConfig ?? null,
        }),
      )
      .catch((e) => toast.error(e.message));
  }, [id]);

  const patch = useCallback(
    (fields) => setDraft((d) => ({ ...d, ...fields })),
    [],
  );
  const setQuestions = useCallback(
    (questions) => setDraft((d) => ({ ...d, formSchema: { questions } })),
    [],
  );

  const save = async () => {
    if (saving) return;
    setSaving(true);
    try {
      const body = toBody(draft);
      if (id) await updateJob(id, body);
      else await createJob(body);
      toast.success(id ? "Posting updated." : "Posting created.");
      navigate(ROUTE_PATHS.RECRUITING_POSTINGS);
    } catch (e) {
      toast.error(e.message);
      setSaving(false);
    }
  };

  return (
    <div className="space-y-6 p-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-slate-900">
          {id ? "Edit posting" : "New posting"}
        </h1>
        <div className="flex gap-2">
          <Button
            variant="outline"
            onClick={() => navigate(ROUTE_PATHS.RECRUITING_POSTINGS)}
          >
            Cancel
          </Button>
          <Button onClick={save} disabled={saving}>
            {saving ? "Saving…" : "Save"}
          </Button>
        </div>
      </div>
      <div className="grid grid-cols-1 gap-8 lg:grid-cols-2">
        <div className="space-y-6">
          <JobBasicsSection
            title={draft.title}
            description={draft.description}
            kind={draft.kind}
            onChange={patch}
          />
          <FormBuilder
            questions={draft.formSchema.questions}
            onChange={setQuestions}
          />
        </div>
        <div className="space-y-2">
          <p className="text-sm font-medium text-slate-700">Preview</p>
          <div className="min-h-24 rounded-md border border-slate-200 bg-slate-50 p-4">
            {draft.formSchema.questions.length === 0 ? (
              <p className="text-sm text-slate-400">Nothing to preview yet.</p>
            ) : (
              <FormRenderer
                questions={draft.formSchema.questions}
                answers={previewAnswers}
                onAnswerChange={(qid, v) =>
                  setPreviewAnswers((a) => ({ ...a, [qid]: v }))
                }
              />
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default PostingEditor;
