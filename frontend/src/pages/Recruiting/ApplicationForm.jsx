import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import PostingApplicantView from "@/pages/Recruiting/components/PostingApplicantView";
import { useAuth } from "@/context/auth/AuthContext.js";
import {
  submitApplication,
  updateApplication,
  getMyLatestProfile,
} from "@/api/recruitingApi";
import { getMyProfile, updateMyProfile } from "@/api/profileApi";
import { ProfileFields } from "@/constants/ApiEndpoints";
import {
  buildNewWriteBackRows,
  buildWriteBackPayload,
} from "@/pages/Recruiting/profileWriteBack";
import { profileToApplicationForm } from "@/pages/Recruiting/profilePrefill";
import { browserTimezone } from "@/components/common/timezoneDefault";
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

/** The fields that make one education row the row it is. */
const EDUCATION_FIELDS = [
  "institution",
  "degree",
  "field",
  "startMonth",
  "startYear",
  "endMonth",
  "endYear",
];

/** The fields that make one experience row the row it is. */
const EXPERIENCE_FIELDS = [
  "title",
  "company",
  "isCurrentlyWorking",
  "startMonth",
  "startYear",
  "endMonth",
  "endYear",
];

/**
 * A comparable rendering of a list of form rows.
 *
 * Order-sensitive on purpose: the order is on screen, so moving a row is a
 * change the candidate can see and should be asked about.
 *
 * @param {object[]} rows
 * @param {string[]} fields
 * @returns {string}
 */
const rowsFingerprint = (rows, fields) =>
  JSON.stringify((rows ?? []).map((row) => fields.map((f) => row?.[f] ?? "")));

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
  const resumeApplicationId = existing?.id ?? seedApplicationId ?? null;
  const existingResume =
    initialResumeObjectKeyRef.current &&
    resume.objectKey === initialResumeObjectKeyRef.current &&
    resumeApplicationId
      ? { applicationId: resumeApplicationId }
      : null;
  // What the profile itself gave, before any fallback filled a blank block
  // and before the candidate touched anything. Comparing against this is what
  // makes "you changed your information" true rather than a guess.
  const profileAtLoadRef = useRef(null);
  // Null until a submission is found to change the profile; then the dialog
  // asking whether to carry those changes over.
  const [pendingSync, setPendingSync] = useState(null);
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
  // Always: the profile is where the block comes from, on every path.
  const [prefillLoading, setPrefillLoading] = useState(true);
  // Which profile blocks this posting puts on screen, and so which the
  // candidate can be said to have reviewed.
  const shownBlocks = {
    education: job.profileConfig?.education !== "off",
    experience: job.profileConfig?.workExperience !== "off",
  };

  useEffect(() => {
    let cancelled = false;
    getMyProfile({
      fields: [ProfileFields.WORK_HISTORY, ProfileFields.EDUCATION],
    })
      .then(async ({ data }) => {
        const fromProfile = profileToApplicationForm(data?.profile);
        profileAtLoadRef.current = fromProfile;
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
    setPendingDiscard(null);
    setPendingSync(null);
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
      // `ApplicationEditDto` forbids extra fields, so `jobId` is only ever
      // sent on create (`ApplicationSubmitDto`), never on edit.
      const res = existing
        ? await updateApplication(existing.id, base)
        : await submitApplication({ jobId: job.id, ...base });
      toast.success("Application submitted.");
      if (sync) await writeBackProfile();
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
    askAboutProfile();
  };

  /**
   * What the candidate changed about themselves, relative to the profile this
   * form started from.
   *
   * Only blocks the posting showed count: a block that was never rendered
   * cannot have been changed here, whatever the form is still holding for it.
   *
   * @returns {boolean} Whether saving would alter their profile at all.
   */
  const profileWouldChange = () => {
    const atLoad = profileAtLoadRef.current;
    // No profile was read, so there is nothing to compare and nothing to
    // offer -- a failed prefill must not turn into a confusing question.
    if (!atLoad) return false;
    const changed = (field) =>
      (profileValue.personal?.[field] ?? "").trim() !==
      (atLoad.personal?.[field] ?? "").trim();
    if (["firstName", "lastName", "linkedin", "timezone"].some(changed)) {
      return true;
    }
    if (
      collects("education") &&
      rowsFingerprint(profileValue.education, EDUCATION_FIELDS) !==
        rowsFingerprint(atLoad.education, EDUCATION_FIELDS)
    ) {
      return true;
    }
    return (
      collects("workExperience") &&
      rowsFingerprint(profileValue.experience, EXPERIENCE_FIELDS) !==
        rowsFingerprint(atLoad.experience, EXPERIENCE_FIELDS)
    );
  };

  /**
   * Ask before carrying this form's version of the candidate into their
   * profile -- and only when there is something to carry.
   *
   * Asked before the application is sent, not after: the form unmounts on
   * success, and a question asked into an unmounted component is a question
   * nobody answers (the same trap that hid résumé upload failures).
   */
  const askAboutProfile = () => {
    if (!profileWouldChange()) {
      send(false);
      return;
    }
    setPendingSync({
      wasEmpty: emptyBlocks(profileAtLoadRef.current, shownBlocks).length > 0,
    });
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
      <Button onClick={submit} disabled={submitting || resumeUploading}>
        {resumeUploading ? "Uploading résumé…" : "Submit application"}
      </Button>
      <Dialog
        open={pendingSync !== null}
        onOpenChange={(open) => !open && setPendingSync(null)}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Update your profile?</DialogTitle>
            <DialogDescription>
              You changed your information while applying. Update your profile
              with it, so your next application starts from it?
            </DialogDescription>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            Your stored education and experience will be replaced by what you
            entered here.
          </p>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => send(false)}
              disabled={submitting}
            >
              Don&apos;t update
            </Button>
            <Button
              variant={pendingSync?.wasEmpty ? "default" : "outline"}
              onClick={() => send(true)}
              disabled={submitting}
            >
              Update &amp; submit
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
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
            <Button onClick={() => askAboutProfile()} disabled={submitting}>
              Submit anyway
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default ApplicationForm;
