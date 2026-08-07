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
import { discardedAnswers } from "@/pages/Recruiting/discardedAnswers";
import { validateApplication } from "@/pages/Recruiting/applicationValidation";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";

/**
 * The server's answer when a create lands on an application that already
 * exists. Matched on the message because that is all the API returns; the
 * consequence of a miss is the old behaviour, not a wrong action.
 */
const ALREADY_APPLIED = /already have an application/i;

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
  // Null until a save is found to cost something; then the list of answers it
  // would delete, which is also what opens the confirm dialog.
  const [pendingDiscard, setPendingDiscard] = useState(null);
  // Empty until the candidate tries to submit. Only ever cleared as fields are
  // fixed, never added to while typing, so a half-filled form does not turn
  // red under someone still working through it.
  const [errors, setErrors] = useState({});
  // A résumé upload runs beside the form, so without this the candidate can
  // submit while their file is still on the wire and land an application that
  // has no résumé attached at all.
  const [resumeUploading, setResumeUploading] = useState(false);
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

  /**
   * Check the answers, and when something is wrong put the page on the first
   * problem instead of sending it.
   *
   * The API reports one failure at a time and names the question by its
   * internal id -- "question q7 is required" -- which appears nowhere on
   * screen. Checking here is what lets the form point at the field.
   *
   * @returns {boolean} True when the application is worth sending.
   */
  const validate = () => {
    const found = validateApplication(
      job.formSchema?.questions ?? [],
      answers,
      { profileConfig: job.profileConfig, profile: profileValue, resume },
    );
    setErrors(found);
    const keys = Object.keys(found);
    if (keys.length === 0) return true;
    toast.error(
      keys.length === 1
        ? "Fix the highlighted field before submitting."
        : `Fix ${keys.length} highlighted fields before submitting.`,
    );
    document
      .querySelector(`[data-error-key="${CSS.escape(keys[0])}"]`)
      ?.scrollIntoView({ block: "center" });
    return false;
  };

  // Clear each error as its field is fixed, the way the profile modals do.
  // Recomputed rather than tracked per keystroke: one answer can hide another
  // question entirely, so an edit in one place resolves an error rendered in
  // another. Narrowed to the keys already on screen, so fixing one problem
  // cannot surface a new one mid-typing.
  useEffect(() => {
    setErrors((shown) => {
      const keys = Object.keys(shown);
      if (keys.length === 0) return shown;
      const current = validateApplication(
        job.formSchema?.questions ?? [],
        answers,
        { profileConfig: job.profileConfig, profile: profileValue, resume },
      );
      const next = {};
      keys.forEach((key) => {
        if (current[key]) next[key] = current[key];
      });
      const unchanged =
        Object.keys(next).length === keys.length &&
        keys.every((key) => next[key] === shown[key]);
      return unchanged ? shown : next;
    });
  }, [answers, profileValue, resume, job]);

  /** Whether the posting asks for a profile section at all. */
  const collects = (key) => job.profileConfig?.[key] !== "off";

  /**
   * Send, having already decided the answers are worth sending and the cost is
   * acceptable.
   *
   * Split from the click handler so the confirm dialog has something to call:
   * everything the server would drop is settled before this runs.
   */
  const send = async () => {
    if (submitting) return;
    setPendingDiscard(null);
    setSubmitting(true);
    try {
      const base = {
        personal: profileValue.personal,
        // A section the posting doesn't collect is not rendered, so whatever
        // rows the form is still holding for it -- carried over from an
        // earlier submission, or autofilled by a résumé parse, which runs
        // regardless -- were never on this candidate's screen. Sending them
        // would store data nobody reviewed. The server strips them too, for a
        // caller that isn't this form.
        education: collects("education") ? profileValue.education : [],
        experience: collects("workExperience") ? profileValue.experience : [],
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
      if (ALREADY_APPLIED.test(e.message ?? "")) {
        // The application exists -- this is a create whose response was lost,
        // typically to a timeout, and every retry from here says the same
        // thing. Move the candidate on rather than leaving them pressing a
        // button that can only ever fail.
        toast.success("Your application is already in.");
        onSubmitted(null);
        return;
      }
      toast.error(e.message);
    } finally {
      setSubmitting(false);
    }
  };

  /**
   * Ask first when saving would throw answers away.
   *
   * The server keeps only what the form is showing and overwrites the
   * submission in place, so a gate the candidate has since changed takes
   * everything under it with no earlier version to recover from. Silent is
   * the wrong default for that; nothing is asked when the save costs nothing,
   * which is nearly every save.
   *
   * Checked before asked: a form that is not going to be accepted should send
   * the candidate back to the bad field, not make them approve a deletion for
   * a submission that then fails anyway.
   */
  const submit = () => {
    if (submitting) return;
    if (!validate()) return;
    const losing = discardedAnswers(job.formSchema?.questions ?? [], answers);
    if (losing.length > 0) {
      setPendingDiscard(losing);
      return;
    }
    send();
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
        errors={errors}
        onResumeUploadingChange={setResumeUploading}
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
      <Button onClick={submit} disabled={submitting || resumeUploading}>
        {resumeUploading ? "Uploading résumé…" : "Submit application"}
      </Button>
      <Dialog
        open={pendingDiscard !== null}
        onOpenChange={(open) => !open && setPendingDiscard(null)}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Some answers will be removed</DialogTitle>
            <DialogDescription>
              The form no longer asks these, so submitting will delete what you
              wrote. This cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <ul className="list-disc space-y-1 pl-5 text-sm">
            {(pendingDiscard ?? []).map((entry) => (
              <li key={entry.key}>{entry.label}</li>
            ))}
          </ul>
          <DialogFooter>
            <Button variant="outline" onClick={() => setPendingDiscard(null)}>
              Keep editing
            </Button>
            <Button onClick={send} disabled={submitting}>
              Submit anyway
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default ApplicationForm;
