import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { useParams, useSearchParams } from "react-router-dom";
import { toast } from "sonner";
import { Check, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Popover,
  PopoverAnchor,
  PopoverContent,
} from "@/components/ui/popover";
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import LoadGate from "@/pages/Recruiting/components/LoadGate";
import { RowList } from "@/pages/Recruiting/components/ApplicationSnapshotRows";
import PeoplePicker from "@/pages/Recruiting/components/PeoplePicker";
import EvaluationRubricForm from "@/pages/Recruiting/applications/EvaluationRubricForm";
import { rubricFor } from "@/pages/Recruiting/applications/evaluationRubric";
import {
  getActiveMentionQuery,
  insertMention,
  renderCommentBody,
} from "@/pages/Recruiting/applications/commentMentions";
import {
  getApplicationDetail,
  getApplicationActivity,
  getApplicationComments,
  getEvaluationsForApplication,
  getJob,
  getMentionableUsers,
  getOtherApplications,
  listInterviewPool,
  setApplicationSubStatus,
  setApplicationRound,
  changeApplicationStage,
  blacklistUser,
  reassignApplication,
  submitEvaluation,
  postComment,
  resumeUrl,
} from "@/api/recruitingApi";
import {
  humanize,
  stageLabel,
  INTERVIEW_STAGES,
} from "@/pages/Recruiting/board/stageFormat";
import { useAuth } from "@/context/auth/AuthContext";
import HowItWorksDialog from "@/pages/Recruiting/components/HowItWorksDialog";
import {
  APPLICATION_OWNER_GUIDE,
  APPLICATION_EVALUATOR_GUIDE,
} from "@/pages/Recruiting/components/guideContent";

/**
 * Advance targets whose assignee picker may be pre-filled from the job's
 * configured `default_assignee_id`, mirroring the backend's
 * `_ASSIGNABLE_DEFAULT_STAGES` (backend/dto/job_config_dto.py): only
 * recruiter_screening/behavioral carry a default; tech/board_review are
 * always picked manually.
 */
const PREFILL_TARGET_STAGES = new Set(["recruiter_screening", "behavioral"]);

/**
 * Rejection reasons offered to the reviewer, mirroring the backend's fixed
 * list (backend/dto/board_dto.py) so the option text sent matches exactly
 * what the server expects.
 */
const REJECT_REASONS = [
  "Insufficient experience",
  "Did not meet the technical bar",
  "Communication concerns",
  "Not aligned with our mission",
  "Accepted another offer",
  "Incomplete application",
  "Candidate declined the offer",
  "Other",
];

/**
 * Allowed sub_status values per pipeline stage, mirroring the backend's
 * SUB_STATUS_SETS (backend/recruiting/stage_machine.py). Stages absent here
 * (terminal stages, or any stage outside the configurable pipeline) have no
 * sub-status, so no selector renders for them.
 */
const SUB_STATUS_SETS = {
  recruiter_screening: ["pending", "in_progress", "evaluated"],
  board_review: ["pending", "in_progress", "evaluated"],
  behavioral: ["pending", "scheduling", "scheduled", "evaluated"],
  tech: ["pending", "scheduling", "scheduled", "evaluated"],
};

/**
 * Compute the stage an application advances to, mirroring the backend's
 * `stage_machine.advance_target`: the next configured pipeline stage; once
 * the current stage is the last one configured, "offer" for an employment
 * job (Offer is a fixed step, never itself configurable) or "hired"
 * directly for an activity job (which has no offer step); "hired" when the
 * current stage is "offer" on an employment job; or null when the current
 * stage isn't part of the job's configured pipeline and isn't an
 * employment job's "offer" either (i.e. it's already a terminal stage).
 *
 * @param {string[]} jobStages The job's configured pipeline stages in order.
 * @param {string} stage The application's current stage.
 * @param {string|null|undefined} kind The job's kind ("employment"|"activity").
 * @returns {string|null} The next stage, "offer", "hired", or null.
 */
const advanceTarget = (jobStages, stage, kind) => {
  if (stage === "offer") return kind === "activity" ? null : "hired";
  const index = jobStages.indexOf(stage);
  if (index === -1) return null;
  if (index < jobStages.length - 1) return jobStages[index + 1];
  return kind === "activity" ? "hired" : "offer";
};

/**
 * Sub-status selector: one button per value allowed for the application's
 * current stage, the active one visually and semantically marked via
 * `aria-pressed`. Renders nothing for stages with no configured sub-status
 * set (terminal stages).
 *
 * @param {{stage: string, subStatus: string|null, disabled: boolean,
 *          onSelect: (value: string) => void}} props
 */
const SubStatusSelector = ({ stage, subStatus, disabled, onSelect }) => {
  const options = SUB_STATUS_SETS[stage];
  if (!options) return null;
  return (
    <div className="flex flex-wrap items-center gap-2">
      <span className="text-sm font-medium text-slate-700">Status:</span>
      {options.map((value) => {
        const isActive = value === subStatus;
        return (
          <Button
            key={value}
            type="button"
            size="sm"
            variant={isActive ? "default" : "outline"}
            aria-pressed={isActive}
            disabled={disabled}
            onClick={() => onSelect(value)}
          >
            {humanize(value)}
          </Button>
        );
      })}
    </div>
  );
};

/**
 * Snapshot of the applicant's submitted personal info: name, LinkedIn, and
 * timezone.
 *
 * @param {{personal: object}} props
 */
const PersonalSection = ({ personal }) => (
  <div className="space-y-1">
    <h2 className="text-sm font-medium text-slate-700">Personal</h2>
    <p className="text-sm text-slate-700">
      {[personal.firstName, personal.lastName].filter(Boolean).join(" ") ||
        "Not provided."}
    </p>
    <p className="text-sm text-slate-700">
      LinkedIn: {personal.linkedin || "Not provided."}
    </p>
    <p className="text-sm text-slate-700">
      Timezone: {personal.timezone || "Not provided."}
    </p>
  </div>
);

/**
 * The submitted answers to the job's form questions, labeled via the detail
 * payload's `formSchema.questions`. Falls back to the raw question id when a
 * question was since removed from the live form schema.
 *
 * @param {{answers: object, questions: {id: string, label: string}[]}} props
 */
const AnswersSection = ({ answers, questions }) => {
  const entries = Object.entries(answers ?? {});
  if (entries.length === 0) return null;
  const labelById = new Map(questions.map((q) => [q.id, q.label]));
  return (
    <div className="space-y-2">
      <h2 className="text-sm font-medium text-slate-700">Answers</h2>
      <ul className="space-y-1">
        {entries.map(([id, value]) => (
          <li key={id} className="text-sm text-slate-700">
            {labelById.get(id) ?? id}: {String(value ?? "—")}
          </li>
        ))}
      </ul>
    </div>
  );
};

/**
 * One field's recorded response inside the read-only evaluation summary:
 * the field label, then its value rendered by type — a pass/fail icon, a
 * 1-5 score badge — followed by any free-text notes. Renders nothing when
 * the evaluator left the field entirely blank.
 *
 * @param {{field: {id: string, label: string, valueType: string},
 *          entry: {value?: boolean|number, notes?: string}|undefined}} props
 */
const EvaluationSummaryRow = ({ field, entry }) => {
  const value = entry?.value;
  const notes = entry?.notes;
  if (value == null && !notes) return null;
  return (
    <div className="space-y-1">
      <p className="text-sm font-medium text-slate-700">{field.label}</p>
      {field.valueType === "pass_fail" && value != null && (
        <span className="inline-flex items-center gap-1 text-sm text-slate-700">
          {value ? (
            <Check aria-label="Pass" className="size-4 text-green-600" />
          ) : (
            <X aria-label="Fail" className="size-4 text-red-600" />
          )}
        </span>
      )}
      {field.valueType === "score" && value != null && (
        <Badge variant="secondary">{value}</Badge>
      )}
      {notes && <p className="text-sm text-slate-600">{notes}</p>}
    </div>
  );
};

/**
 * Resolve an evaluator's display name from the interview pool, falling back
 * to "User {id}" for an evaluator no longer in the active pool (their
 * historical evaluation still needs a label) -- mirrors this page's own
 * `assigneeName` fallback.
 *
 * @param {number} evaluatorId
 * @param {{userId: number, name: string}[]} interviewPool
 * @returns {string}
 */
const evaluatorName = (evaluatorId, interviewPool) =>
  interviewPool.find((u) => u.userId === evaluatorId)?.name ??
  `User ${evaluatorId}`;

/**
 * Read-only summary of every submitted evaluation for an application,
 * newest first (by `id`, a reliable proxy for creation order since it's an
 * auto-incrementing primary key), grouped by stage and, within each stage,
 * by the rubric's own section/field grouping (via `rubricFor`). Each entry
 * is labeled with who submitted it, so a reassignment mid-stage doesn't
 * leave two evaluators' scorecards indistinguishable. Shown to owners so
 * they can see evaluators' scorecards before deciding.
 *
 * @param {{evaluations: {id: number, stage: string, round: number, evaluatorId: number, responses: object}[],
 *          interviewPool: {userId: number, name: string}[]}} props
 */
const EvaluationSummary = ({ evaluations, interviewPool }) => (
  <div className="space-y-4">
    {evaluations.length === 0 ? (
      <p className="text-sm text-slate-400">No evaluations submitted yet.</p>
    ) : (
      [...evaluations]
        .sort((a, b) => b.id - a.id)
        .map((evaluation) => (
          <div key={evaluation.id} className="space-y-3 rounded border p-3">
            <h3 className="text-sm font-medium text-slate-700">
              {humanize(evaluation.stage)} — Round {evaluation.round}
            </h3>
            <p className="text-xs text-slate-500">
              Evaluated by:{" "}
              {evaluatorName(evaluation.evaluatorId, interviewPool)}
            </p>
            {(rubricFor(evaluation.stage) ?? []).map((section) => (
              <div key={section.title} className="space-y-2">
                <h4 className="text-xs font-semibold uppercase text-slate-500">
                  {section.title}
                </h4>
                {section.fields.map((field) => (
                  <EvaluationSummaryRow
                    key={field.id}
                    field={field}
                    entry={evaluation.responses?.[field.id]}
                  />
                ))}
              </div>
            ))}
          </div>
        ))
    )}
  </div>
);

/**
 * Human-readable one-line description of a single activity entry, built
 * from its `details` payload. `details.assigneeName`/`fromAssigneeName`/
 * `toAssigneeName` are present only when the corresponding raw id existed
 * on the underlying event (resolved server-side, read-time only — see
 * `BoardService.get_application_activity`). Similarly,
 * `details.ruleLabel` (on `auto_rejected`) and
 * `details.screenQualifyRuleLabel`/`details.screenAutoHireRuleLabel` (on
 * `application_submitted`) are read-time labels resolved from the
 * corresponding rule id and are optional — older activity rows or rules
 * that have since been removed from the screening config may lack them,
 * in which case the description degrades to the generic unlabeled text.
 * Falls back to the raw `eventType` for anything not explicitly handled,
 * so a future event type still renders something rather than going blank.
 * The actor is rendered separately by `ActivityTimeline`, as a shared
 * trailing suffix — not part of this function's return value.
 *
 * @param {{eventType: string, details: object}} activity
 * @param {string|null|undefined} jobKind The job's kind, so stage names in
 *   the narration match the rest of the page (activity: hired -> Admitted).
 * @returns {string}
 */
const describeActivity = ({ eventType, details }, jobKind) => {
  switch (eventType) {
    case "application_submitted": {
      if (details.screenAutoHireRuleId) {
        return `Submitted — auto-approved by screening rule${
          details.screenAutoHireRuleLabel
            ? ` "${details.screenAutoHireRuleLabel}"`
            : ""
        } (landed on ${stageLabel("hired", jobKind)})`;
      }
      const base = `Submitted — landed on ${humanize(details.stage)}`;
      return details.screenQualifyRuleId
        ? `${base} (auto-qualified by screening rule${
            details.screenQualifyRuleLabel
              ? ` "${details.screenQualifyRuleLabel}"`
              : ""
          })`
        : base;
    }
    case "auto_rejected":
      return details.reason === "screen_rule"
        ? `Automatically rejected by screening rule${
            details.ruleLabel ? ` "${details.ruleLabel}"` : ""
          }`
        : "Automatically rejected (blocked applicant)";
    case "stage_changed":
      if (details.reason) {
        return `Rejected from ${humanize(details.fromStage)}${
          details.note
            ? `: ${details.reason} — ${details.note}`
            : `: ${details.reason}`
        }`;
      }
      return `Advanced from ${humanize(details.fromStage)} to ${stageLabel(details.toStage, jobKind)}${
        details.assigneeName ? `, assigned to ${details.assigneeName}` : ""
      }`;
    case "reassigned":
      return `Reassigned on ${humanize(details.stage)}${
        details.fromAssigneeName ? ` from ${details.fromAssigneeName}` : ""
      } to ${details.toAssigneeName}`;
    case "round_advanced":
      return `Advanced to round ${details.toRound} of ${humanize(details.stage)}${
        details.assigneeName ? `, assigned to ${details.assigneeName}` : ""
      }`;
    case "sub_status_changed":
      return `Status changed from ${humanize(details.fromSubStatus)} to ${humanize(details.toSubStatus)} on ${humanize(details.stage)}`;
    case "evaluation_confirmed":
      return `Confirmed evaluation for round ${details.round} of ${humanize(details.stage)}`;
    case "blacklisted":
      return `Blacklisted and rejected from ${humanize(details.fromStage)}: ${details.reason}`;
    case "auto_assigned":
      return `Automatically assigned to ${details.assigneeName} on ${humanize(details.stage)}`;
    default:
      return humanize(eventType);
  }
};

/**
 * Read-only owner-facing audit timeline for one application: every
 * submission/stage-change/reassign/round-advance/sub-status-change/
 * evaluation-confirm/blacklist event, newest first, each attributed to its
 * actor's resolved display name.
 *
 * @param {{activity: {id: number, eventType: string, details: object,
 *          actorName: string, createdAt: string}[],
 *          jobKind?: string|null}} props
 */
const ActivityTimeline = ({ activity, jobKind }) => (
  <div className="space-y-2">
    {activity.length === 0 ? (
      <p className="text-sm text-slate-400">No activity yet.</p>
    ) : (
      <ul className="space-y-1">
        {activity.map((entry) => (
          <li key={entry.id} className="text-sm text-slate-700">
            <span className="text-slate-500">
              {new Date(entry.createdAt).toLocaleString()}
            </span>{" "}
            — {describeActivity(entry, jobKind)}, by {entry.actorName}
          </li>
        ))}
      </ul>
    )}
  </div>
);

/**
 * A comment thread on an application: read-only history plus a composer
 * that supports @-mentioning the job owner(s) or current-stage assignee.
 * Independent of ApplicationActivityDto -- posting or reading a comment
 * does not create a timeline entry, and comments are never evaluation
 * scores. Comments are immutable once posted (no edit/delete).
 *
 * @param {{comments: {id: number, authorName: string, body: string,
 *          createdAt: string, mentions: {userId: number, name: string}[]}[],
 *          onPost: (body: string) => void, posting: boolean,
 *          mentionableUsers: {userId: number, name: string}[]}} props
 */
const CommentsPanel = ({ comments, onPost, posting, mentionableUsers }) => {
  const [draft, setDraft] = useState("");
  const [mentionQuery, setMentionQuery] = useState(null);
  const textareaRef = useRef(null);
  const pendingCursorRef = useRef(null);

  useLayoutEffect(() => {
    if (pendingCursorRef.current == null || !textareaRef.current) return;
    const pos = pendingCursorRef.current;
    textareaRef.current.setSelectionRange(pos, pos);
    pendingCursorRef.current = null;
  }, [draft]);

  const handlePost = () => {
    if (!draft.trim() || posting) return;
    onPost(draft.trim()).then(
      () => setDraft(""),
      () => {},
    );
  };

  const handleDraftChange = (e) => {
    const value = e.target.value;
    setDraft(value);
    setMentionQuery(getActiveMentionQuery(value, e.target.selectionStart));
  };

  const filteredCandidates = mentionQuery
    ? mentionableUsers.filter((u) =>
        u.name.toLowerCase().includes(mentionQuery.query.toLowerCase()),
      )
    : [];

  const handleSelectMention = (candidate) => {
    const cursorPos = textareaRef.current.selectionStart;
    const { text, cursorPos: nextCursor } = insertMention(
      draft,
      mentionQuery.start,
      cursorPos,
      candidate.userId,
    );
    setDraft(text);
    setMentionQuery(null);
    pendingCursorRef.current = nextCursor;
    textareaRef.current.focus();
  };

  return (
    <div className="space-y-4">
      {comments.length === 0 ? (
        <p className="text-sm text-slate-400">No comments yet.</p>
      ) : (
        <ul className="space-y-2">
          {comments.map((comment) => (
            <li key={comment.id} className="text-sm text-slate-700">
              <span className="text-slate-500">
                {new Date(comment.createdAt).toLocaleString()}
              </span>{" "}
              — {comment.authorName}:{" "}
              {renderCommentBody(comment.body, comment.mentions)}
            </li>
          ))}
        </ul>
      )}
      <div className="flex flex-col gap-2">
        <Popover
          open={Boolean(mentionQuery)}
          onOpenChange={(open) => {
            if (!open) setMentionQuery(null);
          }}
        >
          <PopoverAnchor asChild>
            <Textarea
              ref={textareaRef}
              placeholder="Add a comment…"
              value={draft}
              onChange={handleDraftChange}
              disabled={posting}
            />
          </PopoverAnchor>
          <PopoverContent
            align="start"
            className="w-64 p-0"
            onOpenAutoFocus={(e) => e.preventDefault()}
          >
            <Command>
              <CommandList>
                <CommandEmpty>No one to mention.</CommandEmpty>
                <CommandGroup>
                  {filteredCandidates.map((candidate) => (
                    <CommandItem
                      key={candidate.userId}
                      onSelect={() => handleSelectMention(candidate)}
                    >
                      {candidate.name}
                    </CommandItem>
                  ))}
                </CommandGroup>
              </CommandList>
            </Command>
          </PopoverContent>
        </Popover>
        <Button
          type="button"
          size="sm"
          className="self-end"
          disabled={posting}
          onClick={handlePost}
        >
          Post
        </Button>
      </div>
    </div>
  );
};

/**
 * A candidate's other applications, for the cross-posting aggregation view.
 * Renders nothing when there are none. Each row expands in place — no
 * navigation — into read-only reuse of this page's own snapshot rendering,
 * fed from the row's own payload rather than a fresh detail fetch (the
 * viewer may have no standing on that specific other application's own
 * detail route, only on the one they're currently viewing).
 *
 * Generalized to render either the cross-job "Other applications" list or
 * the same-posting "Previous applications for this posting" history via the
 * `title`/`labelFor` props, so the two sections share one implementation
 * while keeping independent expand state (see the two call sites below).
 *
 * @param {{title: string, otherApplications: {application: object,
 *          jobTitle: string, resumeAvailable: boolean,
 *          evaluations: object[]}[],
 *          interviewPool: {userId: number, name: string}[],
 *          expandedId: number|null, onToggle: (id: number) => void,
 *          labelFor: (other: object) => string}} props
 */
const OtherApplicationsSection = ({
  title,
  otherApplications,
  interviewPool,
  expandedId,
  onToggle,
  labelFor,
}) => {
  if (otherApplications.length === 0) return null;
  return (
    <div className="space-y-2">
      <h2 className="text-sm font-medium text-slate-700">{title}</h2>
      <ul className="space-y-2">
        {otherApplications.map((other) => {
          const isExpanded = other.application.id === expandedId;
          const otherSubmission = other.application.current?.submission ?? {};
          return (
            <li key={other.application.id} className="rounded border p-2">
              <button
                type="button"
                className="flex w-full items-center justify-between text-left text-sm"
                onClick={() => onToggle(other.application.id)}
              >
                <span>{labelFor(other)}</span>
                <span className="text-slate-500">
                  {isExpanded ? "Hide" : "View"}
                </span>
              </button>
              {isExpanded && (
                <div className="mt-3 space-y-4 border-t pt-3">
                  <PersonalSection personal={otherSubmission.personal ?? {}} />
                  <RowList
                    title="Education"
                    rows={otherSubmission.education ?? []}
                  />
                  <RowList
                    title="Experience"
                    rows={otherSubmission.experience ?? []}
                  />
                  <AnswersSection
                    answers={otherSubmission.answers ?? {}}
                    questions={[]}
                  />
                  {other.resumeAvailable && (
                    <iframe
                      src={resumeUrl(other.application.id)}
                      className="h-[400px] w-full rounded border"
                      title="Résumé"
                    />
                  )}
                  <EvaluationSummary
                    evaluations={other.evaluations}
                    interviewPool={interviewPool}
                  />
                </div>
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
};

/**
 * Shared, role-adaptive application detail page at
 * `/recruiting/applications/:applicationId`. Fetches the application detail
 * and its evaluations on mount, then renders a left column (applicant
 * snapshot, personal info, answers, and the résumé when available) shared by
 * everyone, plus a right column that adapts to the viewer:
 *
 * - Anyone who can view (`detail.canView` — owner OR `read.all`) gets the
 *   whole info panel: the sub-status selector, the current assignee, the
 *   evaluations tab, and the timeline tab. Every *actionable* control inside
 *   that panel is instead gated on real ownership (`detail.isOwner`)
 *   specifically, so a `read.all` viewer sees the same information an owner
 *   does but can't act on it: the sub-status buttons render disabled, the
 *   Reassign trigger and the whole "Operate" decision row (Blacklist/Reject/
 *   Advance) don't render at all. For an actual owner, the workflow only
 *   ever moves forward one step at a time, so Advance is a single button
 *   covering both cases: round-advance (via the job's
 *   `pipelineConfig.stages[].rounds`) while rounds remain in the current
 *   stage, then stage-advance once they're exhausted. Advancing into an
 *   interview stage opens a dialog with an optional ("Decide later")
 *   assignee radio-picker, pre-filled from the job's configured
 *   `default_assignee_id` for screening/behavioral stage-advance targets;
 *   leaving it on "Decide later" just advances unassigned, to be picked up
 *   later via Reassign (which, unlike Advance, always requires a pick) — and
 *   a read-only summary of all evaluations. This owner view never shows the
 *   evaluation-filling form, even when the owner is also the current-stage
 *   assignee — grading only happens via the evaluator view below.
 * - The current-stage assignee (`detail.assigneeId === currentUser.userId`)
 *   reaching this page via the `?mode=evaluate` link from My Evaluations
 *   gets ONLY the `EvaluationRubricForm` for the application's stage,
 *   pre-filled from their own draft and locked once confirmed — no owner
 *   actions, even if they're also the owner. Landing in this mode without
 *   being the current assignee (e.g. a stale link, after a reassign) shows a
 *   short explanatory message instead.
 *
 * The rubric form is only mounted after the evaluations fetch resolves (the
 * whole page is gated behind `loaded`), so it never captures a stale/empty
 * `initialResponses` on a pre-fetch render; it is additionally keyed on the
 * caller's confirmed state so a post-submit refresh remounts it cleanly.
 */
const ApplicationDetailPage = () => {
  const { applicationId } = useParams();
  const [searchParams] = useSearchParams();
  const evaluatorMode = searchParams.get("mode") === "evaluate";
  const { user } = useAuth();
  const currentUserId = user?.userId;

  const [detail, setDetail] = useState(null);
  const [evaluations, setEvaluations] = useState([]);
  const [job, setJob] = useState(null);
  const [interviewPool, setInterviewPool] = useState([]);
  const [activity, setActivity] = useState([]);
  const [otherApplications, setOtherApplications] = useState([]);
  const [expandedOtherApplicationId, setExpandedOtherApplicationId] =
    useState(null);
  const [previousApplications, setPreviousApplications] = useState([]);
  const [expandedPreviousId, setExpandedPreviousId] = useState(null);
  const [loaded, setLoaded] = useState(false);
  const [loadError, setLoadError] = useState(false);

  const [advancing, setAdvancing] = useState(false);
  const [advanceAssigneeId, setAdvanceAssigneeId] = useState("");
  const [advanceOpen, setAdvanceOpen] = useState(false);
  const [switchingSubStatus, setSwitchingSubStatus] = useState(false);
  const [scheduleAssigneeWarningOpen, setScheduleAssigneeWarningOpen] =
    useState(false);
  const [advancingRound, setAdvancingRound] = useState(false);
  const [roundAdvanceOpen, setRoundAdvanceOpen] = useState(false);
  const [roundAdvanceAssigneeId, setRoundAdvanceAssigneeId] = useState("");

  const [rejectFormOpen, setRejectFormOpen] = useState(false);
  const [rejectReason, setRejectReason] = useState("");
  const [rejectNote, setRejectNote] = useState("");
  const [rejecting, setRejecting] = useState(false);

  const [reassignOpen, setReassignOpen] = useState(false);
  const [reassignAssigneeId, setReassignAssigneeId] = useState("");
  const [reassigning, setReassigning] = useState(false);

  const [blacklistConfirmOpen, setBlacklistConfirmOpen] = useState(false);
  const [blacklistReason, setBlacklistReason] = useState("");
  const [blacklisting, setBlacklisting] = useState(false);

  const [savingEvaluation, setSavingEvaluation] = useState(false);

  const [comments, setComments] = useState([]);
  const [postingComment, setPostingComment] = useState(false);
  const [mentionableUsers, setMentionableUsers] = useState([]);

  const load = useCallback(() => {
    if (applicationId == null) return;
    setLoadError(false);
    setLoaded(false);
    Promise.all([
      getApplicationDetail(applicationId),
      getEvaluationsForApplication(applicationId),
    ])
      .then(async ([{ data: detailData }, { data: evals }]) => {
        setDetail(detailData);
        setEvaluations(evals ?? []);
        // Job config (per-stage default assignee), the interview pool, and
        // the activity timeline are all read via canView (owner or
        // read.all), not raw isOwner — a read.all viewer sees the same
        // info panel an owner does, just without any action button.
        if (detailData.canView) {
          const [
            { data: jobData },
            { data: pool },
            { data: activityRows },
            otherApplicationsRes,
          ] = await Promise.all([
            getJob(detailData.application.jobId),
            listInterviewPool(),
            getApplicationActivity(applicationId),
            getOtherApplications(applicationId),
          ]);
          setJob(jobData);
          setInterviewPool(pool ?? []);
          setActivity(activityRows ?? []);
          const aggregate = otherApplicationsRes?.data ?? {};
          setOtherApplications(aggregate.otherJobs ?? []);
          setPreviousApplications(aggregate.previousSameJob ?? []);
        }
        // Comments (and who can be @-mentioned in them) are readable by
        // the owner AND the current-stage assignee (unlike job/pool/
        // activity above, which stay owner-only) -- the one fetch here
        // that must also run for an assignee-only viewer.
        if (detailData.isOwner || detailData.assigneeId === currentUserId) {
          const [{ data: commentRows }, { data: mentionable }] =
            await Promise.all([
              getApplicationComments(applicationId),
              getMentionableUsers(applicationId),
            ]);
          setComments(commentRows ?? []);
          setMentionableUsers(mentionable ?? []);
        }
        setLoaded(true);
      })
      .catch((e) => {
        setLoadError(true);
        toast.error(e.message);
      });
  }, [applicationId, currentUserId]);

  useEffect(() => {
    load();
  }, [load]);

  const jobStages = useMemo(
    () => (job?.pipelineConfig?.stages ?? []).map((s) => s.stage),
    [job],
  );

  const next =
    loaded && detail?.isOwner
      ? advanceTarget(jobStages, detail.application.stage, job?.kind)
      : null;
  const isPipelineStage = next !== null;
  const needsAssignee = isPipelineStage && INTERVIEW_STAGES.has(next);

  // Rounds configured for the application's *current* stage (a sibling
  // field to `defaultAssigneeId` on the same per-stage job config entries
  // used for the advance-time prefill above). Stages not configured for
  // multiple rounds, or a job that hasn't loaded yet, default to 1.
  const currentStageRounds =
    loaded && detail
      ? ((job?.pipelineConfig?.stages ?? []).find(
          (s) => s.stage === detail.application.stage,
        )?.rounds ?? 1)
      : 1;
  const canAdvanceRound =
    loaded &&
    detail &&
    currentStageRounds > 1 &&
    (detail.application.currentRound ?? 1) < currentStageRounds;

  // Pre-fill the advance-time assignee picker with the target stage's
  // configured default for screening/behavioral targets (tech/board_review
  // carry none, by design). Runs once the owner's job config has loaded.
  //
  // This page is never remounted between in-page advances on the same
  // application (`handleAdvance` just calls `load()` again), so a value set
  // here for one target stage would otherwise survive into a later target
  // stage that isn't supposed to have one. The non-prefill branches below
  // explicitly clear it whenever the computed target changes to a stage
  // that shouldn't carry a default, so a stale pick can never leak forward.
  useEffect(() => {
    if (!needsAssignee || !PREFILL_TARGET_STAGES.has(next)) {
      setAdvanceAssigneeId("");
      return;
    }
    const entry = (job?.pipelineConfig?.stages ?? []).find(
      (s) => s.stage === next,
    );
    setAdvanceAssigneeId(
      entry?.defaultAssigneeId != null ? String(entry.defaultAssigneeId) : "",
    );
  }, [needsAssignee, next, job]);

  const handleSelectSubStatus = (value) => {
    if (switchingSubStatus) return;
    if (
      value === "scheduled" &&
      ["behavioral", "tech"].includes(detail.application.stage) &&
      detail.assigneeId == null
    ) {
      setScheduleAssigneeWarningOpen(true);
      return;
    }
    setSwitchingSubStatus(true);
    setApplicationSubStatus(applicationId, value)
      .then(() => {
        setDetail((prev) =>
          prev
            ? {
                ...prev,
                application: { ...prev.application, subStatus: value },
              }
            : prev,
        );
      })
      .catch((e) => toast.error(e.message))
      .finally(() => setSwitchingSubStatus(false));
  };

  /**
   * Advance the application to the next round within its current stage
   * (e.g. Tech round 1 -> round 2), for stages configured with more than
   * one round via the job's pipeline config. Patches `currentRound` on the
   * local `detail` state in place, mirroring `handleSelectSubStatus`'s
   * pattern for mutations that don't change the application's stage (so no
   * full reload of the job config/evaluations is needed). No assignee is
   * sent — only used for stages outside `INTERVIEW_STAGES`; currently every
   * configurable stage is an interview stage, so this path is unused today
   * but kept for a future non-interview configurable stage.
   */
  const handleAdvanceRoundDirect = () => {
    if (advancingRound) return;
    const nextRound = (detail.application.currentRound ?? 1) + 1;
    setAdvancingRound(true);
    setApplicationRound(applicationId, nextRound)
      .then(() => {
        setDetail((prev) =>
          prev
            ? {
                ...prev,
                application: { ...prev.application, currentRound: nextRound },
              }
            : prev,
        );
      })
      .catch((e) => toast.error(e.message))
      .finally(() => setAdvancingRound(false));
  };

  /**
   * Open the round-advance flow. Interview stages (`INTERVIEW_STAGES`) open
   * a dialog with an optional assignee picker, mirroring the advance-to-
   * stage flow's `advanceOpen` dialog — leaving it on "Decide later" just
   * advances the round unassigned, to be picked up later via Reassign;
   * any other stage would advance immediately via `handleAdvanceRoundDirect`
   * instead (currently unreachable, since every configurable stage today
   * is an interview stage).
   */
  const handleOpenRoundAdvance = () => {
    if (INTERVIEW_STAGES.has(detail.application.stage)) {
      setRoundAdvanceOpen(true);
      return;
    }
    handleAdvanceRoundDirect();
  };

  const handleCancelRoundAdvance = () => {
    setRoundAdvanceOpen(false);
    setRoundAdvanceAssigneeId("");
  };

  const handleConfirmAdvanceRound = () => {
    if (advancingRound) return;
    const nextRound = (detail.application.currentRound ?? 1) + 1;
    setAdvancingRound(true);
    setApplicationRound(
      applicationId,
      nextRound,
      roundAdvanceAssigneeId ? Number(roundAdvanceAssigneeId) : undefined,
    )
      .then(() => {
        setDetail((prev) =>
          prev
            ? {
                ...prev,
                application: { ...prev.application, currentRound: nextRound },
              }
            : prev,
        );
        setRoundAdvanceOpen(false);
        setRoundAdvanceAssigneeId("");
      })
      .catch((e) => toast.error(e.message))
      .finally(() => setAdvancingRound(false));
  };

  const handleAdvance = (target, assigneeId) => {
    if (advancing) return;
    setAdvancing(true);
    changeApplicationStage(applicationId, {
      toStage: target,
      assigneeId: assigneeId ? Number(assigneeId) : undefined,
    })
      .then(() => {
        toast.success(`Advanced to ${humanize(target)}.`);
        setAdvanceOpen(false);
        load();
      })
      .catch((e) => toast.error(e.message))
      .finally(() => setAdvancing(false));
  };

  const handleCancelReassign = () => {
    setReassignOpen(false);
    setReassignAssigneeId("");
  };

  const handleConfirmReassign = () => {
    if (!reassignAssigneeId || reassigning) return;
    setReassigning(true);
    reassignApplication(applicationId, Number(reassignAssigneeId))
      .then(() => {
        toast.success("Reassigned.");
        setReassignOpen(false);
        setReassignAssigneeId("");
        load();
      })
      .catch((e) => toast.error(e.message))
      .finally(() => setReassigning(false));
  };

  const handleCancelReject = () => {
    setRejectFormOpen(false);
    setRejectReason("");
    setRejectNote("");
  };

  const handleConfirmReject = () => {
    if (!rejectReason || rejecting) return;
    setRejecting(true);
    changeApplicationStage(applicationId, {
      toStage: "rejected",
      reason: rejectReason,
      note: rejectNote.trim() || undefined,
    })
      .then(() => {
        toast.success("Application rejected.");
        handleCancelReject();
        load();
      })
      .catch((e) => toast.error(e.message))
      .finally(() => setRejecting(false));
  };

  const handleCancelBlacklist = () => {
    setBlacklistConfirmOpen(false);
    setBlacklistReason("");
  };

  const handleConfirmBlacklist = () => {
    if (!blacklistReason.trim() || blacklisting) return;
    setBlacklisting(true);
    blacklistUser({
      userId: detail.application.userId,
      applicationId,
      reason: blacklistReason.trim(),
    })
      .then(() => {
        toast.success("Applicant blacklisted.");
        handleCancelBlacklist();
        load();
      })
      .catch((e) => toast.error(e.message))
      .finally(() => setBlacklisting(false));
  };

  const handleSaveDraft = (responses) => {
    if (savingEvaluation) return;
    setSavingEvaluation(true);
    submitEvaluation(applicationId, { responses, confirm: false })
      .then(() => {
        toast.success("Draft saved.");
        load();
      })
      .catch((e) => toast.error(e.message))
      .finally(() => setSavingEvaluation(false));
  };

  const handleConfirmEvaluation = (responses) => {
    if (savingEvaluation) return;
    setSavingEvaluation(true);
    submitEvaluation(applicationId, { responses, confirm: true })
      .then(() => {
        toast.success("Evaluation submitted.");
        load();
      })
      .catch((e) => toast.error(e.message))
      .finally(() => setSavingEvaluation(false));
  };

  const handlePostComment = (body) => {
    if (postingComment) return Promise.resolve();
    setPostingComment(true);
    return postComment(applicationId, { body })
      .then(({ data }) => {
        setComments((prev) => [data, ...prev]);
      })
      .catch((e) => {
        toast.error(e.message);
        throw e;
      })
      .finally(() => setPostingComment(false));
  };

  if (!loaded || !detail) {
    return (
      <LoadGate
        error={loadError}
        errorMessage="Couldn't load this application."
        onRetry={load}
      />
    );
  }

  const submission = detail.application.current?.submission ?? {};
  const isAssignee =
    currentUserId != null && detail.assigneeId === currentUserId;
  const showRubric = evaluatorMode && isAssignee;
  const myEntry = evaluations.find(
    (e) =>
      e.evaluatorId === currentUserId &&
      e.stage === detail.application.stage &&
      e.round === (detail.application.currentRound ?? 1),
  );
  const assigneeName =
    interviewPool.find((u) => u.userId === detail.assigneeId)?.name ??
    (detail.assigneeId != null ? `User ${detail.assigneeId}` : null);

  const guide = evaluatorMode
    ? showRubric
      ? APPLICATION_EVALUATOR_GUIDE
      : null
    : detail.canView
      ? APPLICATION_OWNER_GUIDE
      : null;

  return (
    <div className="flex flex-col gap-6 p-6">
      <div className="space-y-1">
        <div className="flex flex-wrap items-center gap-2">
          <h1 className="text-xl font-semibold text-slate-900">
            {detail.applicantName}
          </h1>
          <Badge variant="secondary">
            {stageLabel(detail.application.stage, job?.kind)}
          </Badge>
          {guide && <HowItWorksDialog {...guide} />}
        </div>
        <p className="text-sm text-slate-600">{detail.applicantEmail}</p>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        {/* Left column: shared applicant snapshot. */}
        <div className="space-y-4">
          <PersonalSection personal={submission.personal ?? {}} />
          <RowList title="Education" rows={submission.education ?? []} />
          <RowList title="Experience" rows={submission.experience ?? []} />
          <AnswersSection
            answers={submission.answers ?? {}}
            questions={detail.formSchema?.questions ?? []}
          />
          {detail.resumeAvailable && (
            <iframe
              src={resumeUrl(applicationId)}
              className="h-[600px] w-full rounded border"
              title="Résumé"
            />
          )}
        </div>

        {/* Right column: role-adaptive. */}
        <div className="space-y-6">
          {detail.canView && !evaluatorMode && (
            <div className="space-y-4">
              <SubStatusSelector
                stage={detail.application.stage}
                subStatus={detail.application.subStatus}
                disabled={switchingSubStatus || !detail.isOwner}
                onSelect={handleSelectSubStatus}
              />
              {(assigneeName || isPipelineStage) && (
                <div className="flex flex-wrap items-center gap-2">
                  {assigneeName && (
                    <p className="text-sm text-slate-700">
                      Assigned to: {assigneeName}
                    </p>
                  )}
                  {isPipelineStage && detail.isOwner && (
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      onClick={() => setReassignOpen(true)}
                    >
                      Reassign
                    </Button>
                  )}
                </div>
              )}

              {detail.isOwner && (
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-sm font-medium text-slate-700">
                    Operate:
                  </span>
                  <Button
                    variant="outline"
                    className="mr-auto"
                    disabled={blacklisting}
                    onClick={() => setBlacklistConfirmOpen(true)}
                  >
                    Blacklist
                  </Button>
                  {isPipelineStage && (
                    <Button
                      variant="outline"
                      onClick={() => setRejectFormOpen(true)}
                    >
                      Reject
                    </Button>
                  )}
                  {canAdvanceRound ? (
                    <Button
                      disabled={advancingRound}
                      onClick={handleOpenRoundAdvance}
                    >
                      Advance to Round{" "}
                      {(detail.application.currentRound ?? 1) + 1}
                    </Button>
                  ) : (
                    isPipelineStage && (
                      <Button
                        disabled={advancing}
                        onClick={() =>
                          needsAssignee
                            ? setAdvanceOpen(true)
                            : handleAdvance(next)
                        }
                      >
                        Advance to {stageLabel(next, job?.kind)}
                      </Button>
                    )
                  )}
                </div>
              )}

              <Tabs defaultValue="evaluations">
                <TabsList>
                  <TabsTrigger value="evaluations">Evaluations</TabsTrigger>
                  <TabsTrigger value="timeline">Timeline</TabsTrigger>
                  <TabsTrigger value="comments">Comments</TabsTrigger>
                </TabsList>
                <TabsContent value="evaluations">
                  <EvaluationSummary
                    evaluations={evaluations}
                    interviewPool={interviewPool}
                  />
                </TabsContent>
                <TabsContent value="timeline">
                  <ActivityTimeline activity={activity} jobKind={job?.kind} />
                </TabsContent>
                <TabsContent value="comments">
                  <CommentsPanel
                    comments={comments}
                    onPost={handlePostComment}
                    posting={postingComment}
                    mentionableUsers={mentionableUsers}
                  />
                </TabsContent>
              </Tabs>

              <OtherApplicationsSection
                title="Previous applications for this posting"
                otherApplications={previousApplications}
                interviewPool={interviewPool}
                expandedId={expandedPreviousId}
                onToggle={(id) =>
                  setExpandedPreviousId((cur) => (cur === id ? null : id))
                }
                labelFor={(other) =>
                  `Applied ${
                    other.application.current?.submittedAt
                      ? new Date(
                          other.application.current.submittedAt,
                        ).toLocaleDateString()
                      : "earlier"
                  } — ${humanize(other.application.stage)}`
                }
              />

              <OtherApplicationsSection
                title="Other applications"
                otherApplications={otherApplications}
                interviewPool={interviewPool}
                expandedId={expandedOtherApplicationId}
                onToggle={(id) =>
                  setExpandedOtherApplicationId((prev) =>
                    prev === id ? null : id,
                  )
                }
                labelFor={(other) =>
                  `${other.jobTitle} — ${humanize(other.application.stage)}`
                }
              />
            </div>
          )}

          {evaluatorMode &&
            (showRubric ? (
              <Tabs defaultValue="evaluation">
                <TabsList>
                  <TabsTrigger value="evaluation">Your evaluation</TabsTrigger>
                  <TabsTrigger value="comments">Comments</TabsTrigger>
                </TabsList>
                <TabsContent value="evaluation">
                  <EvaluationRubricForm
                    key={`eval-${detail.application.stage}-${
                      myEntry?.isConfirmed ? "confirmed" : "draft"
                    }`}
                    stage={detail.application.stage}
                    initialResponses={myEntry?.responses ?? {}}
                    readOnly={Boolean(myEntry?.isConfirmed)}
                    saving={savingEvaluation}
                    onSaveDraft={handleSaveDraft}
                    onConfirm={handleConfirmEvaluation}
                  />
                </TabsContent>
                <TabsContent value="comments">
                  <CommentsPanel
                    comments={comments}
                    onPost={handlePostComment}
                    posting={postingComment}
                    mentionableUsers={mentionableUsers}
                  />
                </TabsContent>
              </Tabs>
            ) : (
              <p className="text-sm text-slate-500">
                You are not currently assigned to evaluate this application.
              </p>
            ))}
        </div>
      </div>

      <Dialog
        open={blacklistConfirmOpen}
        onOpenChange={(nextOpen) => {
          if (!nextOpen) handleCancelBlacklist();
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Blacklist this applicant?</DialogTitle>
          </DialogHeader>
          <Textarea
            placeholder="Reason (required)"
            value={blacklistReason}
            onChange={(e) => setBlacklistReason(e.target.value)}
          />
          <DialogFooter>
            <Button
              variant="outline"
              onClick={handleCancelBlacklist}
              disabled={blacklisting}
            >
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={handleConfirmBlacklist}
              disabled={!blacklistReason.trim() || blacklisting}
            >
              Confirm blacklist
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog
        open={scheduleAssigneeWarningOpen}
        onOpenChange={(nextOpen) => {
          if (!nextOpen) setScheduleAssigneeWarningOpen(false);
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Assignee required</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-slate-700">
            Please assign a reviewer before marking this as Scheduled.
          </p>
          <DialogFooter>
            <Button onClick={() => setScheduleAssigneeWarningOpen(false)}>
              OK
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog
        open={rejectFormOpen}
        onOpenChange={(nextOpen) => {
          if (!nextOpen) handleCancelReject();
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Reject</DialogTitle>
          </DialogHeader>
          <Select value={rejectReason} onValueChange={setRejectReason}>
            <SelectTrigger aria-label="Rejection reason" className="w-full">
              <SelectValue placeholder="Select a reason…" />
            </SelectTrigger>
            <SelectContent className="z-[110]">
              {REJECT_REASONS.map((reason) => (
                <SelectItem key={reason} value={reason}>
                  {reason}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Textarea
            placeholder="Note (optional)"
            value={rejectNote}
            onChange={(e) => setRejectNote(e.target.value)}
          />
          <DialogFooter>
            <Button
              variant="outline"
              onClick={handleCancelReject}
              disabled={rejecting}
            >
              Cancel
            </Button>
            <Button
              onClick={handleConfirmReject}
              disabled={!rejectReason || rejecting}
            >
              Confirm reject
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog
        open={roundAdvanceOpen}
        onOpenChange={(nextOpen) => {
          if (!nextOpen) handleCancelRoundAdvance();
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              Advance to Round {(detail.application.currentRound ?? 1) + 1}
            </DialogTitle>
          </DialogHeader>
          <PeoplePicker
            label="Assignee"
            variant="list"
            noneLabel="Decide later"
            pool={interviewPool}
            value={roundAdvanceAssigneeId || undefined}
            onChange={(v) => setRoundAdvanceAssigneeId(v ? String(v) : "")}
          />
          <DialogFooter>
            <Button
              variant="outline"
              onClick={handleCancelRoundAdvance}
              disabled={advancingRound}
            >
              Cancel
            </Button>
            <Button
              onClick={handleConfirmAdvanceRound}
              disabled={advancingRound}
            >
              Confirm advance round
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog
        open={advanceOpen}
        onOpenChange={(nextOpen) => {
          if (!nextOpen) setAdvanceOpen(false);
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {isPipelineStage
                ? `Advance to ${stageLabel(next, job?.kind)}`
                : "Advance"}
            </DialogTitle>
          </DialogHeader>
          <PeoplePicker
            label="Assignee"
            variant="list"
            noneLabel="Decide later"
            pool={interviewPool}
            value={advanceAssigneeId || undefined}
            onChange={(v) => setAdvanceAssigneeId(v ? String(v) : "")}
          />
          {(next === "behavioral" || next === "tech") && (
            <p className="text-sm text-slate-500">
              You can leave this unassigned for now — an assignee will be
              required before marking this stage as Scheduled.
            </p>
          )}
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setAdvanceOpen(false)}
              disabled={advancing}
            >
              Cancel
            </Button>
            <Button
              onClick={() => handleAdvance(next, advanceAssigneeId)}
              disabled={advancing}
            >
              Confirm advance
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog
        open={reassignOpen}
        onOpenChange={(nextOpen) => {
          if (!nextOpen) handleCancelReassign();
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Reassign</DialogTitle>
          </DialogHeader>
          <PeoplePicker
            label="Assignee"
            variant="list"
            allowNone={false}
            pool={interviewPool}
            value={reassignAssigneeId || undefined}
            onChange={(v) => setReassignAssigneeId(v ? String(v) : "")}
          />
          <DialogFooter>
            <Button
              variant="outline"
              onClick={handleCancelReassign}
              disabled={reassigning}
            >
              Cancel
            </Button>
            <Button
              onClick={handleConfirmReassign}
              disabled={!reassignAssigneeId || reassigning}
            >
              Confirm reassign
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default ApplicationDetailPage;
