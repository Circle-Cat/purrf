import { useState } from "react";
import { toast } from "sonner";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import ResumeUpload from "@/components/common/ResumeUpload";
import ProfileSection from "@/pages/Profile/components/ProfileSection";
import { uploadResume } from "@/api/recruitingApi";
import {
  parsedResumeToProfile,
  mergeParsedIntoProfile,
} from "@/pages/Profile/parsedResumeToProfile";

let uid = 0;
/** Monotonic local row id (unique across this module's lifetime). */
const nextId = () => `rpf-${(uid += 1)}`;

/** A fresh empty education row in the shape ProfileSection expects. */
const emptyEducation = () => ({
  id: nextId(),
  institution: "",
  degree: "",
  field: "",
  startMonth: "",
  startYear: "",
  endMonth: "",
  endYear: "",
});

/** A fresh empty experience row in the shape ProfileSection expects. */
const emptyExperience = () => ({
  id: nextId(),
  title: "",
  company: "",
  isCurrentlyWorking: false,
  startMonth: "",
  startYear: "",
  endMonth: "",
  endYear: "",
});

/** Ensure a merged row carries an id (parsed rows have none). */
const withId = (row) => (row.id == null ? { ...row, id: nextId() } : row);

/** Required/optional marker after a section heading. */
const ReqMark = ({ level }) => {
  if (level === "required") return <span className="text-red-500"> *</span>;
  if (level === "optional")
    return (
      <span className="text-sm font-normal text-muted-foreground">
        {" "}
        (optional)
      </span>
    );
  return null;
};

/**
 * Applicant-facing profile block for a posting. Renders a read-only contact
 * email (auto-filled from the applicant's account on submission — shown as an
 * empty placeholder in this preview-only view), an always-shown basic-info +
 * education + experience editor (reusing ProfileSection, gated by the posting's
 * profileConfig), and a resume upload that always shows as a quick-fill helper
 * (auto-fills the fields below); profileConfig.resume only drives the
 * required/optional marker on the resume-as-deliverable. Owns throwaway state;
 * nothing is submitted.
 *
 * Controlled when both `value` and `onChange` are provided by a parent (e.g.
 * `PostingApplicantView` lifting state for a future submission form); falls
 * back to internal state otherwise so existing render-only usages keep
 * working unchanged.
 *
 * `contactEmail`, when provided, fills the read-only contact-email field
 * (e.g. from the signed-in applicant's account); omitted, the field renders
 * blank with a placeholder, as in a preview.
 *
 * `onResumeStored`, when provided, is called with `{sha256, objectKey}` once
 * an uploaded resume file has been persisted via `uploadResume` -- upload
 * failures toast an error but never block the parse-and-autofill flow below.
 * Omitted, no upload call is made (e.g. preview-only usages).
 *
 * @param {{profileConfig?: {education?: string, workExperience?: string, resume?: string},
 *          value?: {personal: object, education: object[], experience: object[]},
 *          onChange?: (value: {personal: object, education: object[], experience: object[]}) => void,
 *          contactEmail?: string,
 *          onResumeStored?: (resume: {sha256: string, objectKey: string}) => void}} props
 * @returns {JSX.Element}
 */
const RecruitingProfileForm = ({
  profileConfig,
  value: controlledValue,
  onChange,
  contactEmail,
  onResumeStored,
}) => {
  const [internal, setInternal] = useState({
    personal: {},
    education: [emptyEducation()],
    experience: [emptyExperience()],
  });
  const value = controlledValue ?? internal;
  /** Resolve `next` (value or updater fn) against the current value and commit it to the controlling parent or internal state. */
  const setValue = (next) => {
    const resolved = typeof next === "function" ? next(value) : next;
    if (onChange) onChange(resolved);
    else setInternal(resolved);
  };

  const requirements = {
    education: profileConfig?.education ?? "optional",
    experience: profileConfig?.workExperience ?? "optional",
  };
  const resumeLevel = profileConfig?.resume ?? "optional";

  /** Merge a resume-parser result into the current profile value, assigning ids to any new rows. */
  const handleParsed = (parsed) => {
    const merged = mergeParsedIntoProfile(value, parsedResumeToProfile(parsed));
    setValue({
      ...merged,
      education: merged.education.map(withId),
      experience: merged.experience.map(withId),
    });
  };

  /**
   * Persist a resume file via `uploadResume` and forward the resulting
   * `{sha256, objectKey}` to the parent through `onResumeStored`. Runs
   * independently of parsing/autofill above -- a failure here only toasts
   * and never blocks or rolls back the parse-and-autofill flow.
   */
  const handleResumeFile = async (file) => {
    if (!onResumeStored) return;
    try {
      const res = await uploadResume(file);
      const stored = res?.data ?? res;
      onResumeStored({ sha256: stored?.sha256, objectKey: stored?.objectKey });
    } catch {
      toast.error("Couldn't upload your resume file. You can still submit.");
    }
  };

  return (
    <div className="space-y-6">
      <p className="text-sm font-medium text-slate-700">Profile</p>

      <div className="max-w-md space-y-1.5">
        <Label htmlFor="rpf-email">Contact email</Label>
        <Input
          id="rpf-email"
          readOnly
          value={contactEmail ?? ""}
          placeholder="Auto-filled from the applicant's account"
        />
        <p className="text-xs text-muted-foreground">
          Auto-filled from the applicant&apos;s account on submission.
        </p>
      </div>

      <section className="space-y-2">
        <h3 className="text-base font-semibold">
          Resume
          <ReqMark level={resumeLevel} />
        </h3>
        <p className="text-sm text-muted-foreground">
          Have a resume? Upload it to auto-fill the sections below — you can
          edit everything afterward.
          {resumeLevel === "off" &&
            " This posting doesn't collect a resume; uploading only saves you time."}
        </p>
        <ResumeUpload
          onParsed={handleParsed}
          onFile={handleResumeFile}
          showPreview
        />
      </section>

      <ProfileSection
        value={value}
        onChange={setValue}
        requirements={requirements}
        errors={{}}
      />
    </div>
  );
};

export default RecruitingProfileForm;
