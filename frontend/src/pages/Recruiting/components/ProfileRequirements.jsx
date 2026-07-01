import { Badge } from "@/components/ui/badge";

const FIELDS = [
  { key: "education", label: "Education" },
  { key: "workExperience", label: "Work experience" },
  { key: "resume", label: "Resume" },
];

/**
 * Applicant-facing summary of which profile sections a posting requires.
 * Renders a Required/Optional badge per section; `off` (or missing) sections
 * are omitted, and the whole block renders nothing when none apply.
 *
 * @param {{profileConfig?: {education?: string, workExperience?: string, resume?: string}}} props
 */
const ProfileRequirements = ({ profileConfig = {} }) => {
  const shown = FIELDS.filter((f) => {
    const level = profileConfig?.[f.key];
    return level === "required" || level === "optional";
  });
  if (shown.length === 0) return null;

  return (
    <div className="space-y-2">
      <p className="text-sm font-medium text-slate-700">Profile requirements</p>
      <ul className="space-y-1">
        {shown.map((f) => (
          <li
            key={f.key}
            className="flex items-center gap-2 text-sm text-slate-700"
          >
            <span className="w-36">{f.label}</span>
            <Badge
              variant={
                profileConfig[f.key] === "required" ? "default" : "outline"
              }
            >
              {profileConfig[f.key] === "required" ? "Required" : "Optional"}
            </Badge>
          </li>
        ))}
      </ul>
    </div>
  );
};

export default ProfileRequirements;
