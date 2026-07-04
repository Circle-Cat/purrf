import { useCallback, useEffect, useMemo, useState } from "react";
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
import LoadGate from "@/pages/Recruiting/components/LoadGate";
import { RowList } from "@/pages/Recruiting/components/ApplicationSnapshotRows";
import PeoplePicker from "@/pages/Recruiting/components/PeoplePicker";
import EvaluationRubricForm from "@/pages/Recruiting/applications/EvaluationRubricForm";
import { rubricFor } from "@/pages/Recruiting/applications/evaluationRubric";
import {
  getApplicationDetail,
  getApplicationActivity,
  getEvaluationsForApplication,
  getJob,
  listInterviewPool,
  setApplicationSubStatus,
  setApplicationRound,
  changeApplicationStage,
  blacklistUser,
  reassignApplication,
  submitEvaluation,
  resumeUrl,
} from "@/api/recruitingApi";
import {
  humanize,
  INTERVIEW_STAGES,
} from "@/pages/Recruiting/board/stageFormat";
import { useAuth } from "@/context/auth/AuthContext";

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
  offer: ["pending", "evaluated"],
};

/**
 * Compute the stage an application advances to, mirroring the backend's
 * `stage_machine.advance_target`: the next configured pipeline stage, or
 * "hired" once the current stage is the last one configured. Returns null
 * when the current stage isn't part of the job's configured pipeline (i.e.
 * it's already a terminal stage), meaning there's no advance target.
 *
 * @param {string[]} jobStages The job's configured pipeline stages in order.
 * @param {string} stage The application's current stage.
 * @returns {string|null} The next stage, "hired", or null.
 */
const advanceTarget = (jobStages, stage) => {
  const index = jobStages.indexOf(stage);
  if (index === -1) return null;
  return index === jobStages.length - 1 ? "hired" : jobStages[index + 1];
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
 * Read-only summary of every submitted evaluation for an application,
 * grouped by stage and, within each stage, by the rubric's own
 * section/field grouping (via `rubricFor`). Shown to owners so they can see
 * evaluators' scorecards before deciding.
 *
 * @param {{evaluations: {id: number, stage: string, round: number, responses: object}[]}} props
 */
const EvaluationSummary = ({ evaluations }) => (
  <div className="space-y-4">
    {evaluations.length === 0 ? (
      <p className="text-sm text-slate-400">No evaluations submitted yet.</p>
    ) : (
      evaluations.map((evaluation) => (
        <div key={evaluation.id} className="space-y-3 rounded border p-3">
          <h3 className="text-sm font-medium text-slate-700">
            {humanize(evaluation.stage)} — Round {evaluation.round}
          </h3>
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
 * from its `details` payload. Falls back to the raw `eventType` for
 * anything not explicitly handled, so a future event type still renders
 * something rather than going blank.
 *
 * @param {{eventType: string, details: object}} activity
 * @returns {string}
 */
const describeActivity = ({ eventType, details }) => {
  switch (eventType) {
    case "application_submitted":
      return `Submitted — landed on ${humanize(details.stage)}`;
    case "auto_rejected":
      return "Automatically rejected (blocked applicant)";
    case "stage_changed":
      return details.reason
        ? `Rejected from ${humanize(details.fromStage)}${
            details.note
              ? `: ${details.reason} — ${details.note}`
              : `: ${details.reason}`
          }`
        : `Advanced from ${humanize(details.fromStage)} to ${humanize(details.toStage)}`;
    case "reassigned":
      return `Reassigned on ${humanize(details.stage)}`;
    case "round_advanced":
      return `Advanced to round ${details.toRound} of ${humanize(details.stage)}`;
    default:
      return humanize(eventType);
  }
};

/**
 * Read-only owner-facing audit timeline for one application: every
 * submission/stage-change/reassign/round-advance event, newest first, each
 * attributed to its actor's resolved display name.
 *
 * @param {{activity: {id: number, eventType: string, details: object,
 *          actorName: string, createdAt: string}[]}} props
 */
const ActivityTimeline = ({ activity }) => (
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
            — {entry.actorName}: {describeActivity(entry)}
          </li>
        ))}
      </ul>
    )}
  </div>
);

/**
 * Shared, role-adaptive application detail page at
 * `/recruiting/applications/:applicationId`. Fetches the application detail
 * and its evaluations on mount, then renders a left column (applicant
 * snapshot, personal info, answers, and the résumé when available) shared by
 * everyone, plus a right column that adapts to the viewer:
 *
 * - Owners (`detail.isOwner`) get the sub-status selector, an Advance Round
 *   action for stages configured for more than one round (via the job's
 *   `pipelineConfig.stages[].rounds`), the current assignee + Reassign
 *   control, the Advance/Reject/Blacklist decision footer (advancing into an
 *   interview stage opens a dialog with an optional assignee picker,
 *   pre-filled from the job's configured `default_assignee_id` for
 *   screening/behavioral targets — leaving it blank just advances
 *   unassigned, to be picked up later via Reassign), and a read-only summary
 *   of all evaluations. This owner view never shows the evaluation-filling
 *   form, even when the owner is also the current-stage assignee — grading
 *   only happens via the evaluator view below.
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
  const [loaded, setLoaded] = useState(false);
  const [loadError, setLoadError] = useState(false);

  const [advancing, setAdvancing] = useState(false);
  const [advanceAssigneeId, setAdvanceAssigneeId] = useState("");
  const [advanceOpen, setAdvanceOpen] = useState(false);
  const [switchingSubStatus, setSwitchingSubStatus] = useState(false);
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
        // the activity timeline are all owner-only reads (job/pool gated on
        // RECRUITING_JOB_WRITE, activity via row-level ownership), so only
        // an owner fetches them; an assignee-only viewer would be rejected.
        if (detailData.isOwner) {
          const [{ data: jobData }, { data: pool }, { data: activityRows }] =
            await Promise.all([
              getJob(detailData.application.jobId),
              listInterviewPool(),
              getApplicationActivity(applicationId),
            ]);
          setJob(jobData);
          setInterviewPool(pool ?? []);
          setActivity(activityRows ?? []);
        }
        setLoaded(true);
      })
      .catch((e) => {
        setLoadError(true);
        toast.error(e.message);
      });
  }, [applicationId]);

  useEffect(() => {
    load();
  }, [load]);

  const jobStages = useMemo(
    () => (job?.pipelineConfig?.stages ?? []).map((s) => s.stage),
    [job],
  );

  const next =
    loaded && detail?.isOwner
      ? advanceTarget(jobStages, detail.application.stage)
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
   * sent — only used for stages outside `INTERVIEW_STAGES` (e.g. a
   * multi-round `offer`, which has no rubric and isn't assignable).
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
   * Open the round-advance flow. Interview stages (`INTERVIEW_STAGES`) need
   * an assignee picked up front, mirroring the advance-to-stage flow's
   * `needsAssignee`; other multi-round stages (e.g. a multi-round `offer`,
   * which has no rubric and isn't assignable) advance immediately via
   * `handleAdvanceRoundDirect`.
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
    if (!roundAdvanceAssigneeId || advancingRound) return;
    const nextRound = (detail.application.currentRound ?? 1) + 1;
    setAdvancingRound(true);
    setApplicationRound(
      applicationId,
      nextRound,
      Number(roundAdvanceAssigneeId),
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

  return (
    <div className="flex flex-col gap-6 p-6">
      <div className="space-y-1">
        <h1 className="text-xl font-semibold text-slate-900">
          {detail.applicantName}
        </h1>
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
          {detail.isOwner && !evaluatorMode && (
            <div className="space-y-4">
              <SubStatusSelector
                stage={detail.application.stage}
                subStatus={detail.application.subStatus}
                disabled={switchingSubStatus}
                onSelect={handleSelectSubStatus}
              />
              {canAdvanceRound && !roundAdvanceOpen && (
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  disabled={advancingRound}
                  onClick={handleOpenRoundAdvance}
                >
                  Advance to Round {(detail.application.currentRound ?? 1) + 1}
                </Button>
              )}
              {roundAdvanceOpen && (
                <div className="flex flex-col gap-3">
                  <PeoplePicker
                    label="Assignee"
                    pool={interviewPool}
                    value={roundAdvanceAssigneeId || undefined}
                    onChange={(v) =>
                      setRoundAdvanceAssigneeId(v ? String(v) : "")
                    }
                  />
                  <div className="flex justify-end gap-2">
                    <Button
                      variant="outline"
                      onClick={handleCancelRoundAdvance}
                      disabled={advancingRound}
                    >
                      Cancel
                    </Button>
                    <Button
                      onClick={handleConfirmAdvanceRound}
                      disabled={!roundAdvanceAssigneeId || advancingRound}
                    >
                      Confirm advance round
                    </Button>
                  </div>
                </div>
              )}
              {assigneeName && (
                <p className="text-sm text-slate-700">
                  Assigned to: {assigneeName}
                </p>
              )}

              {rejectFormOpen ? (
                <div className="flex flex-col gap-3">
                  <Select value={rejectReason} onValueChange={setRejectReason}>
                    <SelectTrigger
                      aria-label="Rejection reason"
                      className="w-full"
                    >
                      <SelectValue placeholder="Select a reason…" />
                    </SelectTrigger>
                    <SelectContent>
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
                  <div className="flex justify-end gap-2">
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
                  </div>
                </div>
              ) : reassignOpen ? (
                <div className="flex flex-col gap-3">
                  <PeoplePicker
                    label="Assignee"
                    pool={interviewPool}
                    value={reassignAssigneeId || undefined}
                    onChange={(v) => setReassignAssigneeId(v ? String(v) : "")}
                  />
                  <div className="flex justify-end gap-2">
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
                  </div>
                </div>
              ) : (
                <div className="flex flex-wrap items-center gap-2">
                  <Button
                    variant="outline"
                    className="mr-auto"
                    disabled={blacklisting}
                    onClick={() => setBlacklistConfirmOpen(true)}
                  >
                    Blacklist
                  </Button>
                  {isPipelineStage && (
                    <>
                      <Button
                        variant="outline"
                        onClick={() => setReassignOpen(true)}
                      >
                        Reassign
                      </Button>
                      <Button
                        variant="outline"
                        onClick={() => setRejectFormOpen(true)}
                      >
                        Reject
                      </Button>
                      {needsAssignee ? (
                        <Button
                          disabled={advancing}
                          onClick={() => setAdvanceOpen(true)}
                        >
                          Advance to next step
                        </Button>
                      ) : (
                        <Button
                          disabled={advancing}
                          onClick={() => handleAdvance(next)}
                        >
                          Advance to {humanize(next)}
                        </Button>
                      )}
                    </>
                  )}
                </div>
              )}

              <Tabs defaultValue="evaluations">
                <TabsList>
                  <TabsTrigger value="evaluations">Evaluations</TabsTrigger>
                  <TabsTrigger value="timeline">Timeline</TabsTrigger>
                </TabsList>
                <TabsContent value="evaluations">
                  <EvaluationSummary evaluations={evaluations} />
                </TabsContent>
                <TabsContent value="timeline">
                  <ActivityTimeline activity={activity} />
                </TabsContent>
              </Tabs>
            </div>
          )}

          {evaluatorMode &&
            (showRubric ? (
              <div className="space-y-4">
                <h2 className="text-sm font-semibold text-slate-800">
                  Your evaluation
                </h2>
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
              </div>
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
        open={advanceOpen}
        onOpenChange={(nextOpen) => {
          if (!nextOpen) setAdvanceOpen(false);
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {isPipelineStage ? `Advance to ${humanize(next)}` : "Advance"}
            </DialogTitle>
          </DialogHeader>
          <PeoplePicker
            label="Assignee (optional)"
            pool={interviewPool}
            value={advanceAssigneeId || undefined}
            onChange={(v) => setAdvanceAssigneeId(v ? String(v) : "")}
          />
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
    </div>
  );
};

export default ApplicationDetailPage;
