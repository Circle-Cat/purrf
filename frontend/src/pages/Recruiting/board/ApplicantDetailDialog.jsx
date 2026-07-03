import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import LoadGate from "@/pages/Recruiting/components/LoadGate";
import { RowList } from "@/pages/Recruiting/components/ApplicationSnapshotRows";
import {
  getApplicationDetail,
  setApplicationSubStatus,
  changeApplicationStage,
  blacklistUser,
  resumeUrl,
} from "@/api/recruitingApi";
import { humanize } from "@/pages/Recruiting/board/stageFormat";

/**
 * Rejection reasons offered to the reviewer, mirroring the backend's fixed
 * list (backend/dto/board_dto.py) so the option text sent matches
 * exactly what the server expects.
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
 * Compute the stage an application advances to, mirroring the backend's
 * `stage_machine.advance_target`: the next configured pipeline stage, or
 * "hired" once the current stage is the last one configured. Returns null
 * when the current stage isn't part of the job's configured pipeline (i.e.
 * it's already a terminal stage), meaning there's no advance target.
 *
 * @param {string[]} jobStages
 * @param {string} stage
 * @returns {string|null}
 */
const advanceTarget = (jobStages, stage) => {
  const index = jobStages.indexOf(stage);
  if (index === -1) return null;
  return index === jobStages.length - 1 ? "hired" : jobStages[index + 1];
};

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
 * The submitted answers to the job's form questions, labeled via the
 * detail payload's `formSchema.questions`. Falls back to the raw question
 * id when a question was since removed from the live form schema.
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
 * Applicant detail dialog: opened from a board card, shows the full
 * application snapshot (personal info, education, experience, form
 * answers), a resume link when available, a sub-status selector for the
 * application's current pipeline stage, and decision actions
 * (Advance/Reject/Blacklist) in the footer.
 *
 * @param {{applicationId: number|null, open: boolean,
 *          onOpenChange: (open: boolean) => void, onChanged: () => void,
 *          jobStages: string[]}} props
 */
const ApplicantDetailDialog = ({
  applicationId,
  open,
  onOpenChange,
  onChanged,
  jobStages = [],
}) => {
  const [detail, setDetail] = useState(null);
  const [loaded, setLoaded] = useState(false);
  const [loadError, setLoadError] = useState(false);

  const [advancing, setAdvancing] = useState(false);
  const [switchingSubStatus, setSwitchingSubStatus] = useState(false);

  const [rejectFormOpen, setRejectFormOpen] = useState(false);
  const [rejectReason, setRejectReason] = useState("");
  const [rejectNote, setRejectNote] = useState("");
  const [rejecting, setRejecting] = useState(false);

  const [blacklistConfirmOpen, setBlacklistConfirmOpen] = useState(false);
  const [blacklistReason, setBlacklistReason] = useState("");
  const [blacklisting, setBlacklisting] = useState(false);

  const load = useCallback(() => {
    if (applicationId == null) return;
    setLoadError(false);
    setLoaded(false);
    getApplicationDetail(applicationId)
      .then(({ data }) => {
        setDetail(data);
        setLoaded(true);
      })
      .catch((e) => {
        setLoadError(true);
        toast.error(e.message);
      });
  }, [applicationId]);

  useEffect(() => {
    if (open) {
      setAdvancing(false);
      setSwitchingSubStatus(false);
      setRejectFormOpen(false);
      setRejectReason("");
      setRejectNote("");
      setBlacklistConfirmOpen(false);
      setBlacklistReason("");
      setBlacklisting(false);
      load();
    }
  }, [open, load]);

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
        onChanged();
      })
      .catch((e) => toast.error(e.message))
      .finally(() => setSwitchingSubStatus(false));
  };

  const handleAdvance = (next) => {
    if (advancing) return;
    setAdvancing(true);
    changeApplicationStage(applicationId, { toStage: next })
      .then(() => {
        toast.success(`Advanced to ${humanize(next)}.`);
        onChanged();
        onOpenChange(false);
      })
      .catch((e) => toast.error(e.message))
      .finally(() => setAdvancing(false));
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
        onChanged();
        onOpenChange(false);
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
        onChanged();
        setBlacklistConfirmOpen(false);
        setBlacklistReason("");
        onOpenChange(false);
      })
      .catch((e) => toast.error(e.message))
      .finally(() => setBlacklisting(false));
  };

  const next =
    loaded && detail
      ? advanceTarget(jobStages, detail.application.stage)
      : null;
  const isPipelineStage = next !== null;

  return (
    <>
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent className="max-h-[85vh] overflow-y-auto sm:max-w-xl">
          <DialogHeader>
            <DialogTitle>
              {loaded && detail ? detail.applicantName : "Applicant"}
            </DialogTitle>
            {loaded && detail && (
              <>
                <p className="text-sm text-slate-600">
                  {detail.applicantEmail}
                </p>
                {detail.resumeAvailable && (
                  <a
                    href={resumeUrl(applicationId)}
                    target="_blank"
                    rel="noreferrer"
                    className="text-sm text-blue-600 underline"
                  >
                    Resume
                  </a>
                )}
                <SubStatusSelector
                  stage={detail.application.stage}
                  subStatus={detail.application.subStatus}
                  disabled={switchingSubStatus}
                  onSelect={handleSelectSubStatus}
                />
              </>
            )}
          </DialogHeader>
          {!loaded || !detail ? (
            <LoadGate
              error={loadError}
              errorMessage="Couldn't load this application."
              onRetry={load}
            />
          ) : (
            <>
              <div className="space-y-4">
                <PersonalSection
                  personal={
                    detail.application.current?.submission?.personal ?? {}
                  }
                />
                <RowList
                  title="Education"
                  rows={detail.application.current?.submission?.education ?? []}
                />
                <RowList
                  title="Experience"
                  rows={
                    detail.application.current?.submission?.experience ?? []
                  }
                />
                <AnswersSection
                  answers={
                    detail.application.current?.submission?.answers ?? {}
                  }
                  questions={detail.formSchema?.questions ?? []}
                />
              </div>
              {rejectFormOpen ? (
                <DialogFooter className="flex-col items-stretch gap-3 sm:flex-col sm:items-stretch">
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
                </DialogFooter>
              ) : (
                <DialogFooter>
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
                        onClick={() => setRejectFormOpen(true)}
                      >
                        Reject
                      </Button>
                      <Button
                        disabled={advancing}
                        onClick={() => handleAdvance(next)}
                      >
                        Advance to {humanize(next)}
                      </Button>
                    </>
                  )}
                </DialogFooter>
              )}
            </>
          )}
        </DialogContent>
      </Dialog>

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
    </>
  );
};

export default ApplicantDetailDialog;
