import { Button } from "@/components/ui/button";
import { months, years, years60Range, DegreeEnum } from "@/pages/Profile/utils";
import "@/pages/Profile/modals/Modal.css";

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

  return (
    <div className="edit-item-form">
      {/* School */}
      <div className="form-group">
        <label>
          School <span className="required">*</span>
        </label>
        <input
          type="text"
          className={hasError("institution") ? "input-error" : ""}
          value={item.institution || ""}
          onChange={(e) => onChange(item.id, "institution", e.target.value)}
        />
        {hasError("institution") && (
          <span className="error-text">{hasError("institution")}</span>
        )}
      </div>

      {/* Degree */}
      <div className="form-group">
        <label>
          Degree <span className="required">*</span>
        </label>
        <select
          value={item.degree || ""}
          className={hasError("degree") ? "input-error" : ""}
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
          <span className="error-text">{hasError("degree")}</span>
        )}
      </div>

      {/* Field of study */}
      <div className="form-group">
        <label>
          Field of study <span className="required">*</span>
        </label>
        <input
          type="text"
          className={hasError("field") ? "input-error" : ""}
          value={item.field || ""}
          onChange={(e) => onChange(item.id, "field", e.target.value)}
        />
        {hasError("field") && (
          <span className="error-text">{hasError("field")}</span>
        )}
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
          End date <span className="required">*</span>
        </label>
        <div className="date-inputs">
          <select
            value={item.endMonth || ""}
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
            className={hasError("endDate") ? "input-error" : ""}
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
