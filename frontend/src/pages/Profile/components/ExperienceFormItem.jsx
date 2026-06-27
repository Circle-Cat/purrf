import { Button } from "@/components/ui/button";
import { months, years } from "@/pages/Profile/utils";

const LABEL = "mb-2 block text-sm font-semibold text-foreground";
const FIELD_BASE =
  "rounded-[10px] border-2 bg-background px-4 py-3 text-[0.9375rem] text-foreground transition-all focus:border-primary focus:shadow-sm focus:outline-none";
const ERROR_TEXT = "mt-1 block text-xs text-destructive";

/**
 * Controlled form body for a single experience entry. Pure presentation: the
 * parent owns the list and validation. Ticking "currently working" clears and
 * disables the end-date fields (the parent's onChange handles the clearing).
 *
 * @param {Object} props
 * @param {Object} props.item - Experience entry.
 * @param {Object<string, string>} props.errors - Validation errors keyed `${id}-${field}`.
 * @param {(id: string|number, field: string, value: any) => void} props.onChange
 * @param {(id: string|number) => void} props.onDelete
 * @returns {JSX.Element}
 */
export default function ExperienceFormItem({
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
      {/* Title */}
      <div className="mb-5">
        <label className={LABEL}>
          Title <span className="ml-1 text-destructive">*</span>
        </label>
        <input
          type="text"
          className={fieldClass("title")}
          value={item.title || ""}
          onChange={(e) => onChange(item.id, "title", e.target.value)}
        />
        {hasError("title") && (
          <span className={ERROR_TEXT}>{hasError("title")}</span>
        )}
      </div>

      {/* Company or organization */}
      <div className="mb-5">
        <label className={LABEL}>
          Company or organization{" "}
          <span className="ml-1 text-destructive">*</span>
        </label>
        <input
          type="text"
          className={fieldClass("company")}
          value={item.company || ""}
          onChange={(e) => onChange(item.id, "company", e.target.value)}
        />
        {hasError("company") && (
          <span className={ERROR_TEXT}>{hasError("company")}</span>
        )}
      </div>

      {/* Currently working checkbox */}
      <div className="mb-5 flex items-center rounded-lg bg-accent px-4 py-3">
        <input
          type="checkbox"
          id={`current-role-${item.id}`}
          className="mr-2.5 scale-[1.2] accent-primary"
          checked={!!item.isCurrentlyWorking}
          onChange={(e) =>
            onChange(item.id, "isCurrentlyWorking", e.target.checked)
          }
        />
        <label
          htmlFor={`current-role-${item.id}`}
          className="mb-0 cursor-pointer text-[0.9375rem] font-medium text-foreground"
        >
          I am currently working in this role
        </label>
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
          End date{" "}
          {!item.isCurrentlyWorking && (
            <span className="ml-1 text-destructive">*</span>
          )}
        </label>
        <div className="mt-2 flex gap-3">
          <select
            value={item.endMonth || ""}
            disabled={item.isCurrentlyWorking}
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
            disabled={item.isCurrentlyWorking}
            className={fieldClass("endDate", "flex-1")}
            onChange={(e) => onChange(item.id, "endYear", e.target.value)}
          >
            <option value="">Year</option>
            {years.map((y) => (
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
