import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import PostingApplicantView from "@/pages/Recruiting/components/PostingApplicantView";
import { useAuth } from "@/context/auth/AuthContext.js";
import { submitApplication, updateApplication } from "@/api/recruitingApi";
import { getMyProfile, updateMyProfile } from "@/api/profileApi";
import { ProfileFields } from "@/constants/ApiEndpoints";
import {
  buildNewWriteBackRows,
  hasPersonalWriteBackInput,
  buildWriteBackPayload,
} from "@/pages/Recruiting/profileWriteBack";
import { profileToApplicationForm } from "@/pages/Recruiting/profilePrefill";

/**
 * Candidate application form for a published job. Owns the applicant's
 * profile/answers/resume state and submits it via `submitApplication`
 * (create) or `updateApplication` (edit, when `existing` is provided). Both
 * calls share the same base body; `jobId` is added only for the create call,
 * since the edit DTO forbids extra fields and rejects it.
 *
 * `existing` and `seed` both prefill the form but serve different purposes:
 * `existing` is a still-editable application being edited in place (drives
 * the `updateApplication` submit path); `seed` is a prior submission used
 * purely to prefill the form while still submitting via `submitApplication`
 * (create) — used when a rejected candidate reapplies, since the backend's
 * reapply branch lives on the create path, not edit.
 *
 * When there is neither `existing` nor `seed` (a genuinely brand-new
 * application), the form instead blocks its first render on a fetch of the
 * candidate's saved Profile and prefills from that (via
 * `profileToApplicationForm`) — so applying to a second job doesn't start
 * blank when the candidate already wrote their profile back after a first
 * application. A failed fetch just leaves the form at its normal empty
 * state; prefill is a convenience, never a requirement.
 *
 * When "save to my profile" is checked, a successful submission is followed
 * by a best-effort write-back of the form's personal fields and complete
 * education/experience rows to the applicant's profile: the current profile
 * is fetched first, personal fields are merged over the stored user, and each
 * list is OVERWRITTEN with the form's reviewed rows (the applicant reviewed
 * their info while applying, so the reviewed version becomes their profile).
 * A section left empty in the form is not written (it never clears a stored
 * list), and an unchanged list is skipped; nothing is sent when there is
 * neither personal input nor any complete row to write. A write-back failure
 * only toasts a warning and never fails the submission -- `onSubmitted` still
 * fires.
 *
 * @param {{job: object, existing?: object, seed?: object, seedApplicationId?: number,
 *          onSubmitted: (app: object) => void}} props
 */
const ApplicationForm = ({
  job,
  existing,
  seed,
  seedApplicationId,
  onSubmitted,
}) => {
  const { user } = useAuth();
  const priorSubmission = existing?.current ?? seed ?? {};
  const submissionSeed = priorSubmission.submission ?? {};
  const [profileValue, setProfileValue] = useState({
    personal: submissionSeed.personal ?? {},
    education: submissionSeed.education ?? [],
    experience: submissionSeed.experience ?? [],
  });
  const [answers, setAnswers] = useState(submissionSeed.answers ?? {});
  const [resume, setResume] = useState({
    sha256: priorSubmission.resumeSha256 ?? null,
    objectKey: priorSubmission.resumeObjectKey ?? null,
  });
  // Captured once: distinguishes "still showing the inherited résumé
  // reference" from "candidate picked a new file this session" without
  // needing separate boolean state.
  const initialResumeObjectKeyRef = useRef(
    priorSubmission.resumeObjectKey ?? null,
  );
  const resumeApplicationId = existing?.id ?? seedApplicationId ?? null;
  const existingResume =
    initialResumeObjectKeyRef.current &&
    resume.objectKey === initialResumeObjectKeyRef.current &&
    resumeApplicationId
      ? { applicationId: resumeApplicationId }
      : null;
  const [saveToProfile, setSaveToProfile] = useState(!existing);
  const [submitting, setSubmitting] = useState(false);
  const [prefillLoading, setPrefillLoading] = useState(!existing && !seed);

  useEffect(() => {
    if (existing || seed) return;
    let cancelled = false;
    getMyProfile({
      fields: [ProfileFields.WORK_HISTORY, ProfileFields.EDUCATION],
    })
      .then(({ data }) => {
        if (cancelled) return;
        setProfileValue(profileToApplicationForm(data?.profile));
      })
      .catch(() => {
        // Prefill is a convenience; a failure just leaves the form at its
        // normal empty initial state.
      })
      .finally(() => {
        if (!cancelled) setPrefillLoading(false);
      });
    return () => {
      cancelled = true;
    };
    // existing/seed are fixed for the lifetime of a given form instance.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  /**
   * Best-effort write-back of this form's personal fields and complete
   * profile rows. Fetches the stored profile, merges the personal fields over
   * the stored user, and overwrites each education/experience list with the
   * form's reviewed rows (see `buildWriteBackPayload`), then PATCHes only the
   * keys that actually changed. Skips the network entirely when the form has
   * neither complete rows nor any personal input. Failures (fetch or patch)
   * only toast a warning, never throw.
   */
  const writeBackProfile = async () => {
    try {
      const newRows = buildNewWriteBackRows(profileValue);
      const hasRows = newRows.education.length || newRows.workHistory.length;
      if (!hasRows && !hasPersonalWriteBackInput(profileValue.personal)) {
        return;
      }
      const res = await getMyProfile({
        fields: [ProfileFields.WORK_HISTORY, ProfileFields.EDUCATION],
      });
      const payload = buildWriteBackPayload(
        res?.data?.profile,
        newRows,
        profileValue.personal,
      );
      if (!payload) return;
      await updateMyProfile(payload);
    } catch {
      toast.warning(
        "Application submitted, but saving to your profile failed.",
      );
    }
  };

  const submit = async () => {
    if (submitting) return;
    setSubmitting(true);
    try {
      const base = {
        personal: profileValue.personal,
        education: profileValue.education,
        experience: profileValue.experience,
        answers,
        resumeSha256: resume.sha256,
        resumeObjectKey: resume.objectKey,
        saveToProfile,
      };
      // `ApplicationEditDto` forbids extra fields, so `jobId` is only ever
      // sent on create (`ApplicationSubmitDto`), never on edit.
      const res = existing
        ? await updateApplication(existing.id, base)
        : await submitApplication({ jobId: job.id, ...base });
      toast.success("Application submitted.");
      if (saveToProfile) await writeBackProfile();
      onSubmitted(res?.data ?? res);
    } catch (e) {
      toast.error(e.message);
    } finally {
      setSubmitting(false);
    }
  };

  if (prefillLoading) {
    return <p className="p-6 text-sm text-muted-foreground">Loading…</p>;
  }

  return (
    <div className="space-y-4">
      <PostingApplicantView
        title={job.title}
        questions={job.formSchema?.questions ?? []}
        profileConfig={job.profileConfig}
        profileValue={profileValue}
        onProfileChange={setProfileValue}
        answers={answers}
        onAnswerChange={(id, v) => setAnswers((a) => ({ ...a, [id]: v }))}
        contactEmail={user?.email ?? ""}
        onResumeStored={setResume}
        existingResume={existingResume}
      />
      <Label className="flex items-center gap-2 text-sm">
        <Checkbox
          checked={saveToProfile}
          onCheckedChange={(c) => setSaveToProfile(!!c)}
          aria-label="Also save to my profile"
        />
        Also save to my profile
      </Label>
      <Button onClick={submit} disabled={submitting}>
        Submit application
      </Button>
    </div>
  );
};

export default ApplicationForm;
