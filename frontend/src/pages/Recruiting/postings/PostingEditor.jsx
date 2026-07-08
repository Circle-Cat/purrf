import { useCallback, useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import {
  getJob,
  createJob,
  updateJob,
  listInterviewPool,
  listJobOwners,
} from "@/api/recruitingApi";
import { ROUTE_PATHS } from "@/constants/RoutePaths";
import JobBasicsSection from "@/pages/Recruiting/postings/JobBasicsSection";
import FormBuilder from "@/pages/Recruiting/postings/FormBuilder";
import PostingApplicantView from "@/pages/Recruiting/components/PostingApplicantView";
import PipelineConfigEditor from "@/pages/Recruiting/postings/PipelineConfigEditor";
import ScreenRulesEditor from "@/pages/Recruiting/postings/ScreenRulesEditor";
import ProfileConfigEditor from "@/pages/Recruiting/postings/ProfileConfigEditor";
import HowItWorksDialog from "@/pages/Recruiting/components/HowItWorksDialog";
import { POSTING_EDITOR_GUIDE } from "@/pages/Recruiting/components/guideContent";

/** A blank posting draft. */
const BLANK = {
  title: "",
  description: "",
  kind: "activity",
  cooldownDays: null,
  mentorshipRole: null,
  formSchema: { questions: [] },
  pipelineConfig: null,
  screenRules: null,
  profileConfig: null,
};

/**
 * Build the create/update request body from a draft. Config sections not
 * edited in PR1 (pipeline/screen-rules/profile) pass through as loaded.
 * `cooldownDays` and `mentorshipRole` are actively edited and pass through
 * as `null` when unset.
 *
 * @param {object} draft
 * @returns {object}
 */
const toBody = (draft) => ({
  title: draft.title,
  description: draft.description,
  kind: draft.kind,
  cooldownDays: draft.cooldownDays,
  mentorshipRole: draft.mentorshipRole,
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
  const [jobStatus, setJobStatus] = useState(null);
  const [saving, setSaving] = useState(false);
  const [interviewPool, setInterviewPool] = useState([]);
  const [jobOwners, setJobOwners] = useState([]);

  // Kind/mentorship role are only editable while a posting is still a
  // draft; a brand-new (not-yet-loaded) posting has no status yet and is
  // always editable.
  const kindLocked = Boolean(id) && jobStatus != null && jobStatus !== "draft";

  useEffect(() => {
    listInterviewPool()
      .then(({ data }) => setInterviewPool(data ?? []))
      .catch((e) => toast.error(e.message));
    listJobOwners()
      .then(({ data }) => setJobOwners(data ?? []))
      .catch((e) => toast.error(e.message));
  }, []);

  useEffect(() => {
    if (!id) return;
    getJob(id)
      .then(({ data }) => {
        // A CLOSED posting can already have a staged edit in pendingPayload
        // (from a prior edit while still CLOSED); prefill from that draft
        // rather than the live fields so re-editing doesn't silently discard
        // it. kind/mentorshipRole are never part of pendingPayload.
        const source = data.pendingPayload ?? data;
        setJobStatus(data.status ?? null);
        setDraft({
          title: source.title ?? "",
          description: source.description ?? "",
          kind: data.kind ?? "activity",
          cooldownDays: source.cooldownDays ?? null,
          mentorshipRole: data.mentorshipRole ?? null,
          formSchema: source.formSchema ?? { questions: [] },
          pipelineConfig: source.pipelineConfig ?? null,
          screenRules: source.screenRules ?? null,
          profileConfig: source.profileConfig ?? null,
        });
      })
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
        <div className="flex items-center gap-2">
          <HowItWorksDialog {...POSTING_EDITOR_GUIDE} />
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
            cooldownDays={draft.cooldownDays}
            mentorshipRole={draft.mentorshipRole}
            kindLocked={kindLocked}
            onChange={patch}
          />
          <FormBuilder
            questions={draft.formSchema.questions}
            onChange={setQuestions}
          />
          <PipelineConfigEditor
            value={draft.pipelineConfig ?? { stages: [] }}
            onChange={(pipelineConfig) => patch({ pipelineConfig })}
            interviewPool={interviewPool}
            jobOwners={jobOwners}
          />
          <ScreenRulesEditor
            value={draft.screenRules ?? { rules: [] }}
            onChange={(screenRules) => patch({ screenRules })}
            questions={draft.formSchema.questions}
          />
          <ProfileConfigEditor
            value={draft.profileConfig ?? {}}
            onChange={(profileConfig) => patch({ profileConfig })}
          />
        </div>
        <div className="space-y-2">
          <p className="text-sm font-medium text-slate-700">Preview</p>
          <div className="min-h-24 rounded-md border border-slate-200 bg-slate-50 p-4">
            {!draft.title &&
            !draft.description &&
            draft.formSchema.questions.length === 0 ? (
              <p className="text-sm text-slate-400">Nothing to preview yet.</p>
            ) : (
              <PostingApplicantView
                title={draft.title}
                kind={draft.kind}
                description={draft.description}
                questions={draft.formSchema.questions}
                profileConfig={draft.profileConfig}
              />
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default PostingEditor;
