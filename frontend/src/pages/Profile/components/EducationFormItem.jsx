import { Button } from "@/components/ui/button";
import { months, years, years60Range, DegreeEnum } from "@/pages/Profile/utils";

const LABEL = "mb-2 block text-sm font-semibold text-foreground";
const FIELD_BASE =
  "rounded-[10px] border-2 bg-background px-4 py-3 text-[0.9375rem] text-foreground transition-all focus:border-primary focus:shadow-sm focus:outline-none";
const ERROR_TEXT = "mt-1 block text-xs text-destructive";

/**
 * Controlled form body for a single education entry. Pure presentation: the
 * parent owns the list and validation, passing the item, its errors (keyed
 * `${id}-${field}`), and change/delete callbacks.
 *
 * @param {Object} props
 * @param {Object} props.item - Education entry.
 * @param {Object<string, string>} props.errors - Validation errors keyed `${id}-${field}`.
 * @param {(id: string|number, field: string, value: any) => void} props.onChange
 * @param {(id: string|number) => void} props.onDelete
 * @returns {JSX.Element}
 */
export default function EducationFormItem({
  item,
  errors,
  onChange,
  onDelete,
}) {
  const hasError = (field) => errors[`${item.id}-${field}`];
  const fieldClass = (field, width = "w-full") =>
    `${width} ${FIELD_BASE}${hasError(field) ? " border-destructive" : ""}`;

  return (
    <div className="relative mb-5 rounded-xl border-2 bg-muted p-6 transition-all hover:border-accent hover:shadow-sm">
      {/* School */}
      <div className="mb-5">
        <label className={LABEL}>
          School <span className="ml-1 text-destructive">*</span>
        </label>
        <input
          type="text"
          className={fieldClass("institution")}
          value={item.institution || ""}
          onChange={(e) => onChange(item.id, "institution", e.target.value)}
        />
        {hasError("institution") && (
          <span className={ERROR_TEXT}>{hasError("institution")}</span>
        )}
      </div>

      {/* Degree */}
      <div className="mb-5">
        <label className={LABEL}>
          Degree <span className="ml-1 text-destructive">*</span>
        </label>
        <select
          value={item.degree || ""}
          className={fieldClass("degree")}
          onChange={(e) => onChange(item.id, "degree", e.target.value)}
        >
          <option value="">Select Degree</option>
          {Object.values(DegreeEnum).map((degree) => (
            <option key={degree} value={degree}>
              {degree}
            </option>
          ))}
        </select>
        {hasError("degree") && (
          <span className={ERROR_TEXT}>{hasError("degree")}</span>
        )}
      </div>

      {/* Field of study */}
      <div className="mb-5">
        <label className={LABEL}>
          Field of study <span className="ml-1 text-destructive">*</span>
        </label>
        <input
          type="text"
          className={fieldClass("field")}
          value={item.field || ""}
          onChange={(e) => onChange(item.id, "field", e.target.value)}
        />
        {hasError("field") && (
          <span className={ERROR_TEXT}>{hasError("field")}</span>
        )}
      </div>

      {/* Start date */}
      <div className="mb-5">
        <label className={LABEL}>
          Start date <span className="ml-1 text-destructive">*</span>
        </label>
        <div className="mt-2 flex gap-3">
          <select
            value={item.startMonth || ""}
            className={fieldClass("startDate", "flex-1")}
            onChange={(e) => onChange(item.id, "startMonth", e.target.value)}
          >
            <option value="">Month</option>
            {months.map((m) => (
              <option key={m} value={m}>
                {m}
              </option>
            ))}
          </select>
          <select
            value={item.startYear || ""}
            className={fieldClass("startDate", "flex-1")}
            onChange={(e) => onChange(item.id, "startYear", e.target.value)}
          >
            <option value="">Year</option>
            {years.map((y) => (
              <option key={y} value={y}>
                {y}
              </option>
            ))}
          </select>
        </div>
        {hasError("startDate") && (
          <span className={ERROR_TEXT}>{hasError("startDate")}</span>
        )}
      </div>

      {/* End date */}
      <div className="mb-5">
        <label className={LABEL}>
          End date <span className="ml-1 text-destructive">*</span>
        </label>
        <div className="mt-2 flex gap-3">
          <select
            value={item.endMonth || ""}
            className={fieldClass("endDate", "flex-1")}
            onChange={(e) => onChange(item.id, "endMonth", e.target.value)}
          >
            <option value="">Month</option>
            {months.map((m) => (
              <option key={m} value={m}>
                {m}
              </option>
            ))}
          </select>
          <select
            value={item.endYear || ""}
            className={fieldClass("endDate", "flex-1")}
            onChange={(e) => onChange(item.id, "endYear", e.target.value)}
          >
            <option value="">Year</option>
            {years60Range.map((y) => (
              <option key={y} value={y}>
                {y}
              </option>
            ))}
          </select>
        </div>
        {hasError("endDate") && (
          <span className={ERROR_TEXT}>{hasError("endDate")}</span>
        )}
      </div>

      <Button
        variant="destructive"
        size="sm"
        className="absolute right-3 top-3 z-[1]"
        onClick={() => onDelete(item.id)}
      >
        -
      </Button>
    </div>
  );
}
