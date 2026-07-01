import { useState } from "react";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import ResumeUpload from "@/components/common/ResumeUpload";
import ProfileSection from "@/pages/Profile/components/ProfileSection";
import {
  parsedResumeToProfile,
  mergeParsedIntoProfile,
} from "@/pages/Profile/parsedResumeToProfile";
import { useAuth } from "@/context/auth";

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
 * email (auto-filled from the logged-in account), an always-shown basic-info +
 * education + experience editor (reusing ProfileSection, gated by the posting's
 * profileConfig), and a resume upload entry when resume is not "off". Owns
 * throwaway state; nothing is submitted.
 *
 * @param {{profileConfig?: {education?: string, workExperience?: string, resume?: string}}} props
 * @returns {JSX.Element}
 */
const RecruitingProfileForm = ({ profileConfig }) => {
  const { user } = useAuth() ?? {};
  const [value, setValue] = useState({
    personal: {},
    education: [emptyEducation()],
    experience: [emptyExperience()],
  });

  const requirements = {
    education: profileConfig?.education ?? "optional",
    experience: profileConfig?.workExperience ?? "optional",
  };
  const resumeLevel = profileConfig?.resume ?? "optional";

  const handleParsed = (parsed) => {
    const merged = mergeParsedIntoProfile(value, parsedResumeToProfile(parsed));
    setValue({
      ...merged,
      education: merged.education.map(withId),
      experience: merged.experience.map(withId),
    });
  };

  return (
    <div className="space-y-6">
      <p className="text-sm font-medium text-slate-700">Profile</p>

      <div className="max-w-md space-y-1.5">
        <Label htmlFor="rpf-email">Contact email</Label>
        <Input id="rpf-email" readOnly value={user?.email ?? ""} />
        <p className="text-xs text-muted-foreground">From your account.</p>
      </div>

      {resumeLevel !== "off" && (
        <section className="space-y-3">
          <h3 className="text-base font-semibold">
            Resume
            <ReqMark level={resumeLevel} />
          </h3>
          <ResumeUpload onParsed={handleParsed} />
        </section>
      )}

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
