import ResumeUpload from "@/components/common/ResumeUpload";
import ProfileSection from "@/pages/Profile/components/ProfileSection";
import {
  parsedResumeToProfile,
  mergeParsedIntoProfile,
} from "@/pages/Profile/parsedResumeToProfile";

/**
 * A profile editor with a resume-upload prefill on top. Uploading a resume
 * overlays the parsed fields onto the current `value` (existing values win
 * where the resume has nothing), then the user edits inline. Controlled: the
 * parent owns `value`/`onChange`.
 *
 * @param {Object} props
 * @param {{ personal: object, education: object[], experience: object[] }} props.value
 * @param {(next: object) => void} props.onChange
 * @param {{ education: string, experience: string }} [props.requirements]
 * @returns {JSX.Element}
 */
export default function ResumePrefilledProfileSection({
  value,
  onChange,
  requirements,
}) {
  const handleParsed = (parsed) =>
    onChange(mergeParsedIntoProfile(value, parsedResumeToProfile(parsed)));

  return (
    <div className="space-y-6">
      <ResumeUpload onParsed={handleParsed} />
      <ProfileSection
        value={value}
        onChange={onChange}
        requirements={requirements}
      />
    </div>
  );
}
