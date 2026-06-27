import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import TimezoneSelector from "@/components/common/TimezoneSelector";
import EducationFormItem from "@/pages/Profile/components/EducationFormItem";
import ExperienceFormItem from "@/pages/Profile/components/ExperienceFormItem";

/** A fresh empty education row. */
const emptyEducation = () => ({
  id: `new-${Date.now()}-${Math.round(performance.now())}`,
  institution: "",
  degree: "",
  field: "",
  startMonth: "",
  startYear: "",
  endMonth: "",
  endYear: "",
});

/** A fresh empty experience row. */
const emptyExperience = () => ({
  id: `new-${Date.now()}-${Math.round(performance.now())}`,
  title: "",
  company: "",
  isCurrentlyWorking: false,
  startMonth: "",
  startYear: "",
  endMonth: "",
  endYear: "",
});

/** Required-marker shown after an optional/required section heading. */
function ReqMark({ level }) {
  if (level === "required") return <span className="text-red-500"> *</span>;
  if (level === "optional")
    return (
      <span className="text-sm font-normal text-muted-foreground">
        {" "}
        (optional)
      </span>
    );
  return null;
}

/**
 * Controlled inline profile editor: a personal sub-form plus education and
 * experience lists (each gated by `requirements`). The parent owns `value` and
 * receives the full next value on every edit via `onChange`. Reuses the same
 * `EducationFormItem` / `ExperienceFormItem` as the Profile edit modals.
 *
 * @param {Object} props
 * @param {{ personal: object, education: object[], experience: object[] }} props.value
 * @param {(next: object) => void} props.onChange
 * @param {{ education: string, experience: string }} [props.requirements]
 * @param {Object<string,string>} [props.errors]
 * @returns {JSX.Element}
 */
export default function ProfileSection({
  value,
  onChange,
  requirements = { education: "optional", experience: "optional" },
  errors = {},
}) {
  const { personal, education, experience } = value;

  const setPersonal = (field, v) =>
    onChange({ ...value, personal: { ...personal, [field]: v } });

  const changeEducation = (id, field, v) =>
    onChange({
      ...value,
      education: education.map((row) =>
        row.id === id ? { ...row, [field]: v } : row,
      ),
    });
  const addEducation = () =>
    onChange({ ...value, education: [...education, emptyEducation()] });
  const deleteEducation = (id) =>
    onChange({ ...value, education: education.filter((r) => r.id !== id) });

  const changeExperience = (id, field, v) =>
    onChange({
      ...value,
      experience: experience.map((row) => {
        if (row.id !== id) return row;
        if (field === "isCurrentlyWorking" && v === true) {
          return {
            ...row,
            isCurrentlyWorking: true,
            endMonth: "",
            endYear: "",
          };
        }
        return { ...row, [field]: v };
      }),
    });
  const addExperience = () =>
    onChange({ ...value, experience: [...experience, emptyExperience()] });
  const deleteExperience = (id) =>
    onChange({ ...value, experience: experience.filter((r) => r.id !== id) });

  return (
    <div className="space-y-8">
      {/* Personal */}
      <section className="space-y-4">
        <h3 className="text-base font-semibold">Personal</h3>
        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-1.5">
            <Label htmlFor="ps-firstName">First name</Label>
            <Input
              id="ps-firstName"
              value={personal.firstName || ""}
              onChange={(e) => setPersonal("firstName", e.target.value)}
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="ps-lastName">Last name</Label>
            <Input
              id="ps-lastName"
              value={personal.lastName || ""}
              onChange={(e) => setPersonal("lastName", e.target.value)}
            />
          </div>
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="ps-linkedin">LinkedIn</Label>
          <Input
            id="ps-linkedin"
            value={personal.linkedin || ""}
            onChange={(e) => setPersonal("linkedin", e.target.value)}
          />
        </div>
        <div className="space-y-1.5">
          <Label>Timezone</Label>
          <TimezoneSelector
            value={personal.timezone || ""}
            onChange={(opt) => setPersonal("timezone", opt?.value ?? "")}
          />
        </div>
      </section>

      {/* Education */}
      {requirements.education !== "off" && (
        <section className="space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-base font-semibold">
              Education
              <ReqMark level={requirements.education} />
            </h3>
            <Button
              type="button"
              size="sm"
              aria-label="Add education"
              onClick={addEducation}
            >
              +
            </Button>
          </div>
          {education.map((item) => (
            <EducationFormItem
              key={item.id}
              item={item}
              errors={errors}
              onChange={changeEducation}
              onDelete={deleteEducation}
            />
          ))}
        </section>
      )}

      {/* Experience */}
      {requirements.experience !== "off" && (
        <section className="space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-base font-semibold">
              Experience
              <ReqMark level={requirements.experience} />
            </h3>
            <Button
              type="button"
              size="sm"
              aria-label="Add experience"
              onClick={addExperience}
            >
              +
            </Button>
          </div>
          {experience.map((item) => (
            <ExperienceFormItem
              key={item.id}
              item={item}
              errors={errors}
              onChange={changeExperience}
              onDelete={deleteExperience}
            />
          ))}
        </section>
      )}
    </div>
  );
}
