import { Label } from "@/components/ui/label";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";

const FIELDS = [
  { key: "education", label: "Education" },
  { key: "workExperience", label: "Work experience" },
  { key: "resume", label: "Resume" },
];
const LEVELS = ["required", "optional", "off"];

/**
 * Per-posting profile-section requirement levels (education / work experience /
 * resume), each required | optional | off.
 *
 * @param {{value: {education?: string, workExperience?: string, resume?: string},
 *          onChange: (next: object) => void}} props
 */
const ProfileConfigEditor = ({ value = {}, onChange }) => {
  const levelOf = (key) => value[key] ?? "optional";
  const set = (key, level) => onChange({ ...value, [key]: level });

  return (
    <div className="space-y-3">
      <p className="text-sm font-medium text-slate-700">Profile requirements</p>
      {FIELDS.map((f) => (
        <div key={f.key} className="flex items-center gap-4">
          <span className="w-36 text-sm text-slate-700">{f.label}</span>
          <RadioGroup
            className="flex gap-4"
            value={levelOf(f.key)}
            onValueChange={(level) => set(f.key, level)}
          >
            {LEVELS.map((level) => (
              <Label
                key={level}
                className="flex items-center gap-1 text-sm capitalize"
              >
                <RadioGroupItem
                  value={level}
                  aria-label={`${f.label} ${level}`}
                />
                {level}
              </Label>
            ))}
          </RadioGroup>
        </div>
      ))}
    </div>
  );
};

export default ProfileConfigEditor;
