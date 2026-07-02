import { useState } from "react";
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
  mergeWriteBackPayload,
} from "@/pages/Recruiting/profileWriteBack";

/**
 * Candidate application form for a published job. Owns the applicant's
 * profile/answers/resume state and submits it via `submitApplication`
 * (create) or `updateApplication` (edit, when `existing` is provided). Both
 * calls share the same base body; `jobId` is added only for the create call,
 * since the edit DTO forbids extra fields and rejects it.
 *
 * When "save to my profile" is checked, a successful submission is followed
 * by a best-effort write-back of complete education/experience rows to the
 * applicant's profile: the current profile is fetched first and the new rows
 * are MERGED into its lists (the backend PATCH fully replaces each list, so
 * sending only the new rows would wipe existing entries). Nothing is sent
 * when the form has no complete new rows or every new row already exists in
 * the profile. A write-back failure only toasts a warning and never fails
 * the submission -- `onSubmitted` still fires.
 *
 * @param {{job: object, existing?: object, onSubmitted: (app: object) => void}} props
 */
const ApplicationForm = ({ job, existing, onSubmitted }) => {
  const { user } = useAuth();
  const seed = existing?.current?.submission ?? {};
  const [profileValue, setProfileValue] = useState({
    personal: seed.personal ?? {},
    education: seed.education ?? [],
    experience: seed.experience ?? [],
  });
  const [answers, setAnswers] = useState(seed.answers ?? {});
  const [resume, setResume] = useState({
    sha256: existing?.current?.resumeSha256 ?? null,
    objectKey: existing?.current?.resumeObjectKey ?? null,
  });
  const [saveToProfile, setSaveToProfile] = useState(!existing);
  const [submitting, setSubmitting] = useState(false);

  /**
   * Best-effort merge write-back of this form's complete profile rows.
   * Fetches the stored profile, merges the new rows in (preserving existing
   * rows and their ids -- the backend PATCH replaces each list wholesale),
   * and PATCHes only lists that actually gained a row. Skips the network
   * entirely when the form has no complete new rows. Failures (fetch or
   * patch) only toast a warning, never throw.
   */
  const writeBackProfile = async () => {
    try {
      const newRows = buildNewWriteBackRows(profileValue);
      if (!newRows.education.length && !newRows.workHistory.length) return;
      const res = await getMyProfile({
        fields: [ProfileFields.WORK_HISTORY, ProfileFields.EDUCATION],
      });
      const payload = mergeWriteBackPayload(res?.data?.profile, newRows);
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

  return (
    <div className="space-y-4">
      <PostingApplicantView
        title={job.title}
        kind={job.kind}
        description={job.description}
        questions={job.formSchema?.questions ?? []}
        profileConfig={job.profileConfig}
        profileValue={profileValue}
        onProfileChange={setProfileValue}
        answers={answers}
        onAnswerChange={(id, v) => setAnswers((a) => ({ ...a, [id]: v }))}
        contactEmail={user?.email ?? ""}
        onResumeStored={setResume}
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
