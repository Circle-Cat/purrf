import { Button } from "@/components/ui/button";
import { months, years } from "@/pages/Profile/utils";
import "@/pages/Profile/modals/Modal.css";

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

  return (
    <div className="edit-item-form">
      {/* Title */}
      <div className="form-group">
        <label>
          Title <span className="required">*</span>
        </label>
        <input
          type="text"
          className={hasError("title") ? "input-error" : ""}
          value={item.title || ""}
          onChange={(e) => onChange(item.id, "title", e.target.value)}
        />
        {hasError("title") && (
          <span className="error-text">{hasError("title")}</span>
        )}
      </div>

      {/* Company or organization */}
      <div className="form-group">
        <label>
          Company or organization <span className="required">*</span>
        </label>
        <input
          type="text"
          className={hasError("company") ? "input-error" : ""}
          value={item.company || ""}
          onChange={(e) => onChange(item.id, "company", e.target.value)}
        />
        {hasError("company") && (
          <span className="error-text">{hasError("company")}</span>
        )}
      </div>

      {/* Currently working checkbox */}
      <div className="form-group-checkbox">
        <input
          type="checkbox"
          id={`current-role-${item.id}`}
          checked={!!item.isCurrentlyWorking}
          onChange={(e) =>
            onChange(item.id, "isCurrentlyWorking", e.target.checked)
          }
        />
        <label htmlFor={`current-role-${item.id}`}>
          I am currently working in this role
        </label>
      </div>

      {/* Start date */}
      <div className="form-group date-group">
        <label>
          Start date <span className="required">*</span>
        </label>
        <div className="date-inputs">
          <select
            value={item.startMonth || ""}
            className={hasError("startDate") ? "input-error" : ""}
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
            className={hasError("startDate") ? "input-error" : ""}
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
          <span className="error-text">{hasError("startDate")}</span>
        )}
      </div>

      {/* End date */}
      <div className="form-group date-group">
        <label>
          End date{" "}
          {!item.isCurrentlyWorking && <span className="required">*</span>}
        </label>
        <div className="date-inputs">
          <select
            value={item.endMonth || ""}
            disabled={item.isCurrentlyWorking}
            className={hasError("endDate") ? "input-error" : ""}
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
            className={hasError("endDate") ? "input-error" : ""}
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
          <span className="error-text">{hasError("endDate")}</span>
        )}
      </div>

      <Button
        variant="destructive"
        size="sm"
        className="delete-btn"
        onClick={() => onDelete(item.id)}
      >
        -
      </Button>
    </div>
  );
}
