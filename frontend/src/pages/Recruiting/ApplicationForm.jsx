import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import PostingApplicantView from "@/pages/Recruiting/components/PostingApplicantView";
import ApplicationNextStepsDialog from "@/pages/Recruiting/components/ApplicationNextStepsDialog";
import { useAuth } from "@/context/auth/AuthContext.js";
import {
  submitApplication,
  getMyLatestProfile,
  getMyApplicationDraft,
  saveApplicationDraft,
} from "@/api/recruitingApi";
import { getMyProfile, updateMyProfile } from "@/api/profileApi";
import { ProfileFields } from "@/constants/ApiEndpoints";
import {
  buildNewWriteBackRows,
  buildWriteBackPayload,
} from "@/pages/Recruiting/profileWriteBack";
import { profileToApplicationForm } from "@/pages/Recruiting/profilePrefill";
import { browserTimezone } from "@/components/common/timezoneDefault";
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
 * Which of the profile's blocks have nothing in them.
 *
 * `personal` counts as empty only when there is no name at all: a timezone
 * defaults from the browser, so it is never the deciding field.
 *
 * @param {{personal: object, education: object[], experience: object[]}} value
 * @param {{education?: boolean, experience?: boolean}} [shown] Blocks the
 *   posting renders; a hidden one is never reported as worth filling.
 * @returns {string[]} Any of "personal", "education", "experience".
 */
const emptyBlocks = (value, shown = {}) => {
  const blanks = [];
  const { firstName, lastName } = value.personal ?? {};
  if (!firstName?.trim() && !lastName?.trim()) blanks.push("personal");
  // A block the posting does not show is not worth filling: nobody would see
  // it, and rows nobody saw are exactly what must never reach the profile.
  if (shown.education !== false && (value.education ?? []).length === 0) {
    blanks.push("education");
  }
  if (shown.experience !== false && (value.experience ?? []).length === 0) {
    blanks.push("experience");
  }
  return blanks;
};

/**
 * Fill the named blocks from an earlier submission, leaving the rest alone.
 *
 * Rows from a submission carry that submission's own ids; they are local to a
 * form and never a profile row id, which is what makes them safe to reuse
 * here.
 *
 * @param {object} fromProfile What the profile gave.
 * @param {object|undefined} sent The blocks of the latest submission.
 * @param {string[]} blanks Which blocks to fill.
 * @returns {object} The merged form value.
 */
const withFallback = (fromProfile, sent, blanks) => {
  const filled = { ...fromProfile };
  if (blanks.includes("personal") && sent?.personal) {
    filled.personal = { ...fromProfile.personal, ...sent.personal };
  }
  if (blanks.includes("education") && sent?.education?.length) {
    filled.education = sent.education;
  }
  if (blanks.includes("experience") && sent?.experience?.length) {
    filled.experience = sent.experience;
  }
  return filled;
};

/**
 * The caller's saved draft for a job, or null. Never throws: a draft is a
 * convenience, and failing to read one must leave a usable form.
 *
 * @param {number} jobId
 * @returns {Promise<object|null>}
 */
const loadDraft = async (jobId) => {
  try {
    const res = await getMyApplicationDraft(jobId);
    return res?.data ?? null;
  } catch {
    return null;
  }
};

/**
 * Candidate application form for a published job. Owns the applicant's
 * profile/answers/resume state and submits it via `submitApplication`.
 *
 * `seed` is a prior submission used to prefill the form when a rejected
 * candidate reapplies; the reapply still goes through `submitApplication`,
 * since the backend's reapply branch lives on the create path.
 *
 * The form always blocks its first render on a fetch of the candidate's
 * saved Profile and prefills from that (via `profileToApplicationForm`) — so
 * applying to a second job doesn't start blank when the candidate already
 * wrote their profile back after a first application. A failed fetch just
 * leaves the form at its normal empty state; prefill is a convenience, never
 * a requirement.
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
 * A new application to a mentorship posting (an activity posting with a
 * mentorship role) does not call `onSubmitted` straight away: it first
 * explains what comes after applying, since admission alone gets nobody
 * matched. That dialog leads to `onViewApplication` (falling back to
 * `onSubmitted`) or to the Personal Dashboard. Every other posting goes
 * straight to `onSubmitted`.
 *
 * The application can also be saved as a private draft and finished later.
 * Its saved draft, when there is one, is read alongside the profile and wins
 * over every other prefill, résumé reference included. Saving a draft checks
 * nothing; submitting is confirmed first, since a submitted application
 * cannot be changed. Whether to write the form back to the profile is a
 * checkbox, ticked by default.
 *
 * @param {{job: object, seed?: object, seedApplicationId?: number,
 *          onSubmitted: (app: object) => void,
 *          onViewApplication?: () => void}} props
 */
const ApplicationForm = ({
  job,
  seed,
  seedApplicationId,
  onSubmitted,
  onViewApplication,
}) => {
  const { user } = useAuth();
  const priorSubmission = seed ?? {};
  const submissionSeed = priorSubmission.submission ?? {};
  const [profileValue, setProfileValue] = useState({
    personal: {
      ...(submissionSeed.personal ?? {}),
      // A submission from before this defaulted may carry no zone at all.
      timezone: submissionSeed.personal?.timezone || browserTimezone(),
    },
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
  const resumeApplicationId = seedApplicationId ?? null;
  const existingResume =
    initialResumeObjectKeyRef.current &&
    resume.objectKey === initialResumeObjectKeyRef.current &&
    resumeApplicationId
      ? { applicationId: resumeApplicationId }
      : null;
  const [submitting, setSubmitting] = useState(false);
  // Set once a new mentorship application is in: `{app}` while the
  // what-comes-next dialog is up.
  const [nextStepsFor, setNextStepsFor] = useState(null);
  // Empty until the candidate tries to submit. Only ever cleared as fields are
  // fixed, never added to while typing, so a half-filled form does not turn
  // red under someone still working through it.
  const [errors, setErrors] = useState({});
  // A résumé upload runs beside the form, so without this the candidate can
  // submit while their file is still on the wire and land an application that
  // has no résumé attached at all.
  const [resumeUploading, setResumeUploading] = useState(false);
  // Always: the profile is where the block comes from, on every path.
  const [prefillLoading, setPrefillLoading] = useState(true);
  // The profile write-back choice, the submit confirmation, a draft save in
  // flight, and the résumé key a loaded draft carried (shown as attached
  // while it is still the one on the form).
  const [saveToProfile, setSaveToProfile] = useState(true);
  const [confirmingSubmit, setConfirmingSubmit] = useState(false);
  const [savingDraft, setSavingDraft] = useState(false);
  const [draftResumeKey, setDraftResumeKey] = useState(null);
  const draftResumeOnFile =
    !existingResume &&
    Boolean(draftResumeKey) &&
    resume.objectKey === draftResumeKey;
  // Which profile blocks this posting puts on screen, and so which the
  // candidate can be said to have reviewed.
  const shownBlocks = {
    education: job.profileConfig?.education !== "off",
    experience: job.profileConfig?.workExperience !== "off",
  };

  /**
   * Put a saved draft on the form, replacing whatever the profile gave.
   *
   * @param {object} draft As `getMyApplicationDraft` returns it.
   */
  const applyDraft = (draft) => {
    setProfileValue({
      personal: {
        ...(draft.personal ?? {}),
        timezone: draft.personal?.timezone || browserTimezone(),
      },
      education: draft.education ?? [],
      experience: draft.experience ?? [],
    });
    setAnswers(draft.answers ?? {});
    setResume({
      sha256: draft.resumeSha256 ?? null,
      objectKey: draft.resumeObjectKey ?? null,
    });
    setDraftResumeKey(draft.resumeObjectKey ?? null);
  };

  useEffect(() => {
    let cancelled = false;
    // Started now so it runs beside the profile read, applied after it so
    // the draft wins.
    const draftLoad = loadDraft(job.id);
    getMyProfile({
      fields: [ProfileFields.WORK_HISTORY, ProfileFields.EDUCATION],
    })
      .then(async ({ data }) => {
        const fromProfile = profileToApplicationForm(data?.profile);
        const blanks = emptyBlocks(fromProfile, shownBlocks);
        if (blanks.length === 0) return fromProfile;
        // Applied before but never saved it: start them from what they
        // already sent once rather than from a blank form. Guarded on its
        // own -- this is the convenience on top of the convenience, and
        // losing it must not cost them what the profile did give.
        try {
          const { data: sent } = await getMyLatestProfile();
          return withFallback(fromProfile, sent, blanks);
        } catch {
          return fromProfile;
        }
      })
      .then((value) => {
        if (!cancelled) setProfileValue(value);
      })
      .catch(() => {
        // Prefill is a convenience; a failure just leaves the form at its
        // normal empty initial state.
      })
      .then(() => draftLoad)
      .then((draft) => {
        if (!cancelled && draft) applyDraft(draft);
      })
      .finally(() => {
        if (!cancelled) setPrefillLoading(false);
      });
    return () => {
      cancelled = true;
    };
    // Read once per form instance: the profile is the source, and a later
    // change to it must not yank the block out from under someone typing.
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
      const res = await getMyProfile({
        fields: [ProfileFields.WORK_HISTORY, ProfileFields.EDUCATION],
      });
      const payload = buildWriteBackPayload(
        res?.data?.profile,
        newRows,
        profileValue.personal,
        {
          education: collects("education"),
          workExperience: collects("workExperience"),
        },
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
  const send = async (sync) => {
    if (submitting) return;
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
        saveToProfile: sync,
      };
      const res = await submitApplication({ jobId: job.id, ...base });
      const submitted = res?.data ?? res;
      const explainNextSteps =
        job.kind === "activity" && Boolean(job.mentorshipRole);
      // The dialog's own title says it was submitted; a toast would repeat it.
      if (!explainNextSteps) {
        toast.success("Application submitted.");
      }
      if (sync) await writeBackProfile();
      if (explainNextSteps) {
        setNextStepsFor({ app: submitted });
      } else {
        onSubmitted(submitted);
      }
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

  /** Check the form, then ask the candidate to confirm before sending. */
  const submit = () => {
    if (submitting) return;
    if (!validate()) return;
    setConfirmingSubmit(true);
  };

  /** Send a new application once the candidate confirms it. */
  const confirmSubmit = () => {
    setConfirmingSubmit(false);
    send(saveToProfile);
  };

  /**
   * Save the form as it stands as the candidate's private draft. Nothing is
   * checked: a draft is allowed to be incomplete. Stays on the page.
   */
  const saveDraft = async () => {
    if (savingDraft || submitting) return;
    setSavingDraft(true);
    try {
      await saveApplicationDraft({
        jobId: job.id,
        personal: profileValue.personal,
        education: profileValue.education,
        experience: profileValue.experience,
        answers,
        resumeSha256: resume.sha256 ?? null,
        resumeObjectKey: resume.objectKey ?? null,
      });
      toast.success("Draft saved.");
    } catch (e) {
      toast.error(e.message);
    } finally {
      setSavingDraft(false);
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
        errors={errors}
        onResumeUploadingChange={setResumeUploading}
        onResumeStored={setResume}
        existingResume={existingResume}
        draftResumeOnFile={draftResumeOnFile}
        afterProfile={
          <div className="flex items-start gap-2 rounded-md border border-amber-300 bg-amber-50 p-3">
            <Checkbox
              id="application-save-to-profile"
              className="mt-0.5"
              checked={saveToProfile}
              onCheckedChange={(checked) => setSaveToProfile(checked === true)}
            />
            <div className="space-y-1">
              <Label htmlFor="application-save-to-profile">
                Also save these changes to my profile
              </Label>
              <p className="text-xs text-muted-foreground">
                Your profile will be updated with what you entered here.
              </p>
            </div>
          </div>
        }
      />
      <div className="flex flex-wrap items-center gap-2">
        <Button onClick={submit} disabled={submitting || resumeUploading}>
          {resumeUploading ? "Uploading résumé…" : "Submit application"}
        </Button>
        <Button
          variant="outline"
          onClick={saveDraft}
          disabled={savingDraft || submitting || resumeUploading}
        >
          Save draft
        </Button>
      </div>
      <p className="text-xs text-muted-foreground">
        Only you can see a draft. You can&apos;t change your application after
        you submit it.
      </p>
      <Dialog
        open={confirmingSubmit}
        onOpenChange={(open) => !open && setConfirmingSubmit(false)}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Submit your application?</DialogTitle>
            <DialogDescription>
              You can&apos;t change it after you submit. If you&apos;re not
              ready, save a draft and come back later.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setConfirmingSubmit(false)}
            >
              Keep editing
            </Button>
            <Button onClick={confirmSubmit} disabled={submitting}>
              Submit
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
      {nextStepsFor && (
        <ApplicationNextStepsDialog
          open
          onViewApplication={() =>
            onViewApplication
              ? onViewApplication()
              : onSubmitted(nextStepsFor.app)
          }
        />
      )}
    </div>
  );
};

export default ApplicationForm;
