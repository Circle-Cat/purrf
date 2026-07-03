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
import LoadGate from "@/pages/Recruiting/components/LoadGate";
import { RowList } from "@/pages/Recruiting/components/ApplicationSnapshotRows";
import {
  getApplicationDetail,
  setApplicationSubStatus,
  resumeUrl,
} from "@/api/recruitingApi";

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

/** "in_progress" -> "In progress". */
const humanize = (value) => {
  const spaced = value.replaceAll("_", " ");
  return spaced.charAt(0).toUpperCase() + spaced.slice(1);
};

/**
 * Sub-status selector: one button per value allowed for the application's
 * current stage, the active one visually and semantically marked via
 * `aria-pressed`. Renders nothing for stages with no configured sub-status
 * set (terminal stages).
 *
 * @param {{stage: string, subStatus: string|null, onSelect: (value: string) => void}} props
 */
const SubStatusSelector = ({ stage, subStatus, onSelect }) => {
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
 * answers), a resume link when available, and a sub-status selector for
 * the application's current pipeline stage. A later task adds
 * Advance/Reject/Blacklist actions to the footer.
 *
 * @param {{applicationId: number|null, open: boolean,
 *          onOpenChange: (open: boolean) => void, onChanged: () => void}} props
 */
const ApplicantDetailDialog = ({
  applicationId,
  open,
  onOpenChange,
  onChanged,
}) => {
  const [detail, setDetail] = useState(null);
  const [loaded, setLoaded] = useState(false);
  const [loadError, setLoadError] = useState(false);

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
      load();
    }
  }, [open, load]);

  const handleSelectSubStatus = (value) => {
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
      .catch((e) => toast.error(e.message));
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[85vh] overflow-y-auto sm:max-w-xl">
        <DialogHeader>
          <DialogTitle>
            {loaded && detail ? detail.applicantName : "Applicant"}
          </DialogTitle>
          {loaded && detail && (
            <>
              <p className="text-sm text-slate-600">{detail.applicantEmail}</p>
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
                rows={detail.application.current?.submission?.experience ?? []}
              />
              <AnswersSection
                answers={detail.application.current?.submission?.answers ?? {}}
                questions={detail.formSchema?.questions ?? []}
              />
            </div>
            <DialogFooter />
          </>
        )}
      </DialogContent>
    </Dialog>
  );
};

export default ApplicantDetailDialog;
