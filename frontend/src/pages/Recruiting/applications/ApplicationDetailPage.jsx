import { useCallback, useEffect, useMemo, useState } from "react";
import { useParams } from "react-router-dom";
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
import LoadGate from "@/pages/Recruiting/components/LoadGate";
import { RowList } from "@/pages/Recruiting/components/ApplicationSnapshotRows";
import PeoplePicker from "@/pages/Recruiting/components/PeoplePicker";
import EvaluationRubricForm from "@/pages/Recruiting/applications/EvaluationRubricForm";
import { rubricFor } from "@/pages/Recruiting/applications/evaluationRubric";
import {
  getApplicationDetail,
  getEvaluationsForApplication,
  getJob,
  listInterviewPool,
  setApplicationSubStatus,
  changeApplicationStage,
  blacklistUser,
  reassignApplication,
  submitEvaluation,
  resumeUrl,
} from "@/api/recruitingApi";
import { humanize } from "@/pages/Recruiting/board/stageFormat";
import { useAuth } from "@/context/auth/AuthContext";

/**
 * Stages that carry an interview assignment/evaluation, mirroring the
 * backend's `INTERVIEW_STAGES` (backend/recruiting/board_service.py). An
 * advance into one of these requires an assignee up front.
 */
const INTERVIEW_STAGES = new Set([
  "recruiter_screening",
  "behavioral",
  "tech",
  "board_review",
]);

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
 * @param {{evaluations: {id: number, stage: string, responses: object}[]}} props
 */
const EvaluationSummary = ({ evaluations }) => (
  <div className="space-y-4">
    <h2 className="text-sm font-semibold text-slate-800">Evaluations</h2>
    {evaluations.length === 0 ? (
      <p className="text-sm text-slate-400">No evaluations submitted yet.</p>
    ) : (
      evaluations.map((evaluation) => (
        <div key={evaluation.id} className="space-y-3 rounded border p-3">
          <h3 className="text-sm font-medium text-slate-700">
            {humanize(evaluation.stage)}
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
 * Shared, role-adaptive application detail page at
 * `/recruiting/applications/:applicationId`. Fetches the application detail
 * and its evaluations on mount, then renders a left column (applicant
 * snapshot, personal info, answers, and the résumé when available) shared by
 * everyone, plus a right column that adapts to the viewer:
 *
 * - Owners (`detail.isOwner`) get the sub-status selector, the current
 *   assignee + Reassign control, the Advance/Reject/Blacklist decision
 *   footer (with the advance-time assignee picker pre-filled from the job's
 *   configured `default_assignee_id` for screening/behavioral targets), and
 *   a read-only summary of all evaluations.
 * - The current-stage assignee (`detail.assigneeId === currentUser.userId`)
 *   gets the `EvaluationRubricForm` for the application's stage, pre-filled
 *   from their own draft and locked once confirmed.
 * - A viewer who is both sees both areas.
 *
 * The rubric form is only mounted after the evaluations fetch resolves (the
 * whole page is gated behind `loaded`), so it never captures a stale/empty
 * `initialResponses` on a pre-fetch render; it is additionally keyed on the
 * caller's confirmed state so a post-submit refresh remounts it cleanly.
 */
const ApplicationDetailPage = () => {
  const { applicationId } = useParams();
  const { user } = useAuth();
  const currentUserId = user?.userId;

  const [detail, setDetail] = useState(null);
  const [evaluations, setEvaluations] = useState([]);
  const [job, setJob] = useState(null);
  const [interviewPool, setInterviewPool] = useState([]);
  const [loaded, setLoaded] = useState(false);
  const [loadError, setLoadError] = useState(false);

  const [advancing, setAdvancing] = useState(false);
  const [advanceAssigneeId, setAdvanceAssigneeId] = useState("");
  const [switchingSubStatus, setSwitchingSubStatus] = useState(false);

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
        // Job config (per-stage default assignee) and the interview pool are
        // owner-only reads (both gated on RECRUITING_JOB_WRITE), so only an
        // owner fetches them; an assignee-only viewer would be rejected.
        if (detailData.isOwner) {
          const [{ data: jobData }, { data: pool }] = await Promise.all([
            getJob(detailData.application.jobId),
            listInterviewPool(),
          ]);
          setJob(jobData);
          setInterviewPool(pool ?? []);
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

  // Pre-fill the advance-time assignee picker with the target stage's
  // configured default for screening/behavioral targets (tech/board_review
  // carry none, by design). Runs once the owner's job config has loaded.
  useEffect(() => {
    if (!needsAssignee || !PREFILL_TARGET_STAGES.has(next)) return;
    const entry = (job?.pipelineConfig?.stages ?? []).find(
      (s) => s.stage === next,
    );
    if (entry?.defaultAssigneeId != null) {
      setAdvanceAssigneeId(String(entry.defaultAssigneeId));
    }
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

  const handleAdvance = (target, assigneeId) => {
    if (advancing) return;
    setAdvancing(true);
    changeApplicationStage(applicationId, {
      toStage: target,
      assigneeId: assigneeId ? Number(assigneeId) : undefined,
    })
      .then(() => {
        toast.success(`Advanced to ${humanize(target)}.`);
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
    submitEvaluation(applicationId, { responses, confirm: false })
      .then(() => {
        toast.success("Draft saved.");
        load();
      })
      .catch((e) => toast.error(e.message));
  };

  const handleConfirmEvaluation = (responses) => {
    submitEvaluation(applicationId, { responses, confirm: true })
      .then(() => {
        toast.success("Evaluation submitted.");
        load();
      })
      .catch((e) => toast.error(e.message));
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
  const myEntry = evaluations.find(
    (e) =>
      e.evaluatorId === currentUserId && e.stage === detail.application.stage,
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
          {detail.isOwner && (
            <div className="space-y-4">
              <SubStatusSelector
                stage={detail.application.stage}
                subStatus={detail.application.subStatus}
                disabled={switchingSubStatus}
                onSelect={handleSelectSubStatus}
              />
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
                        <>
                          <PeoplePicker
                            label="Assignee"
                            pool={interviewPool}
                            value={advanceAssigneeId || undefined}
                            onChange={(v) =>
                              setAdvanceAssigneeId(v ? String(v) : "")
                            }
                          />
                          <Button
                            disabled={!advanceAssigneeId || advancing}
                            onClick={() =>
                              handleAdvance(next, advanceAssigneeId)
                            }
                          >
                            Confirm advance
                          </Button>
                        </>
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

              <EvaluationSummary evaluations={evaluations} />
            </div>
          )}

          {isAssignee && (
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
                onSaveDraft={handleSaveDraft}
                onConfirm={handleConfirmEvaluation}
              />
            </div>
          )}
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
    </div>
  );
};

export default ApplicationDetailPage;
