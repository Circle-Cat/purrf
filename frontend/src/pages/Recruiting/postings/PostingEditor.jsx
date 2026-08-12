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
import { validatePosting } from "@/pages/Recruiting/postings/postingValidation";
import PendingNotice from "@/pages/Recruiting/components/PendingNotice";
import { GLOSSARY } from "@/pages/Recruiting/components/glossary";

/** A blank posting draft. */
const BLANK = {
  title: "",
  description: "",
  kind: "activity",
  cooldownDays: 0,
  mentorshipRole: null,
  formSchema: { questions: [] },
  pipelineConfig: null,
  screenRules: null,
  profileConfig: null,
};

/**
 * Build the create/update request body from a draft. Config sections not
 * edited here (pipeline/screen-rules/profile) pass through as loaded.
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
  // Empty until the author tries to save. Errors are never added while they
  // type -- only cleared as each one is resolved -- so the page does not turn
  // red under a half-finished question.
  const [errors, setErrors] = useState({});
  const [interviewPool, setInterviewPool] = useState([]);
  const [jobOwners, setJobOwners] = useState([]);

  // Kind/mentorship role are only editable while a posting is still a
  // draft; a brand-new (not-yet-loaded) posting has no status yet and is
  // always editable.
  const kindLocked = Boolean(id) && jobStatus != null && jobStatus !== "draft";
  // Editing anything that has a live version stages the change rather than
  // applying it; a draft has nothing live to protect.
  const isLive = jobStatus != null && jobStatus !== "draft";

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
          cooldownDays: source.cooldownDays ?? 0,
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
  const setFormSchema = useCallback(
    (formSchema) => setDraft((d) => ({ ...d, formSchema })),
    [],
  );

  // Clear each error the moment its field is fixed, the way the profile
  // modals do. Recomputed from the draft rather than tracked per keystroke:
  // one option's text is referenced by every question it reveals, so an edit
  // in one card can resolve an error rendered in another. Narrowed to the
  // keys already on screen, so resolving one problem cannot surface a new one
  // mid-typing.
  useEffect(() => {
    setErrors((shown) => {
      const keys = Object.keys(shown);
      if (keys.length === 0) return shown;
      const current = validatePosting(draft);
      const next = {};
      keys.forEach((key) => {
        if (current[key]) next[key] = current[key];
      });
      const unchanged =
        Object.keys(next).length === keys.length &&
        keys.every((key) => next[key] === shown[key]);
      return unchanged ? shown : next;
    });
  }, [draft]);

  /**
   * Check the draft and, when anything is wrong, put the page on the first
   * problem instead of sending it.
   *
   * Reporting locally is not only faster than a round trip: the API answers
   * with one sentence naming an internal question id, and nothing about it
   * says which of a dozen cards to look at.
   *
   * @returns {boolean} True when the draft is worth sending.
   */
  const validate = () => {
    const found = validatePosting(draft);
    setErrors(found);
    const keys = Object.keys(found);
    if (keys.length === 0) return true;
    toast.error(
      keys.length === 1
        ? "Fix the highlighted field before saving."
        : `Fix ${keys.length} highlighted fields before saving.`,
    );
    document
      .querySelector(`[data-error-key="${CSS.escape(keys[0])}"]`)
      ?.scrollIntoView({ block: "center" });
    return false;
  };

  const save = async () => {
    if (saving) return;
    if (!validate()) return;
    setSaving(true);
    try {
      const body = toBody(draft);
      // Both paths land on the posting's own page: saving only ever produces a
      // draft (or stages an edit), and everything the author does next --
      // submitting for review above all -- lives there, not on the list.
      let savedId = id;
      if (id) {
        await updateJob(id, body);
      } else {
        const { data } = await createJob(body);
        savedId = data.id;
      }
      toast.success(id ? "Posting updated." : "Posting created.");
      navigate(ROUTE_PATHS.RECRUITING_POSTING_DETAIL(savedId));
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
      </div>
      {/* Most authors expect editing a live posting to change what applicants
          see immediately. It does not, and nothing on this form said so. */}
      {isLive && (
        <PendingNotice
          headline={GLOSSARY["posting.staged_edit"].label}
          detail={GLOSSARY["posting.staged_edit"].hint}
        />
      )}
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
            errors={errors}
          />
          <FormBuilder
            formSchema={draft.formSchema}
            onChange={setFormSchema}
            errors={errors}
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
            errors={errors}
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
      {/* After the form, not above it: the editor is long enough that saving
          from the top means scrolling back up past everything just edited. */}
      <div className="flex flex-wrap items-center justify-end gap-2">
        {/* Beside the button, because the belief it corrects -- that saving
            publishes -- is acted on at the moment of clicking it. */}
        <p className="mr-auto text-xs text-slate-500">
          Saving never publishes. It writes a draft, or stages an edit to a live
          posting; submit it for review from the posting&apos;s own page when it
          is ready.
        </p>
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
  );
};

export default PostingEditor;
