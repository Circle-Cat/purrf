import React, { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import "@/pages/Profile/modals/Modal.css";
import {
  months,
  years,
  years60Range,
  formatDateFromParts,
  getDateScore,
  DegreeEnum,
} from "@/pages/Profile/utils";

/**
 * Form item for editing a single education entry.
 *
 * @param {Object} props
 * @param {Object} props.item - Education data.
 * @param {Object<string, string>} props.errors - Validation errors keyed by `${id}-${field}`.
 * @param {(id: string|number, field: string, value: any) => void} props.onChange - Change handler.
 * @param {(id: string|number) => void} props.onDelete - Delete handler.
 */
const EducationFormItem = ({ item, errors, onChange, onDelete }) => {
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
};

/**
 * Modal for editing the education list.
 *
 * @param {Object} props
 * @param {boolean} props.isOpen - Whether the modal is open.
 * @param {() => void} props.onClose - Close handler.
 * @param {Array<Object>} props.initialData - Initial education data.
 * @param {(payload: any) => Promise<void>} props.onSave - Save handler.
 */
const EducationEditModal = ({ isOpen, onClose, initialData, onSave }) => {
  const [list, setList] = useState([]);
  const [errors, setErrors] = useState({});
  const [isSaving, setIsSaving] = useState(false);

  // Initialize state when modal opens
  useEffect(() => {
    if (isOpen && initialData) {
      setList(structuredClone(initialData));
      setErrors({});
      setIsSaving(false);
    }
  }, [isOpen, initialData]);

  if (!isOpen) return null;

  /**
   * Handle field change for an education item and clear related errors.
   *
   * @param {string|number} id - Item id.
   * @param {string} field - Field name.
   * @param {*} value - New value.
   */
  const handleChange = (id, field, value) => {
    setList((prev) =>
      prev.map((item) => {
        if (item.id !== id) return item;

        return { ...item, [field]: value };
      }),
    );

    // Clear related validation errors automatically
    setErrors((prev) => {
      const next = { ...prev };
      delete next[`${id}-${field}`];
      if (field === "startMonth" || field === "startYear") {
        delete next[`${id}-startDate`];
      }
      return next;
    });
  };

  const handleAdd = () => {
    const newItem = {
      id: `new-${Date.now()}`,
      institution: "",
      degree: "",
      field: "",
      startMonth: "",
      startYear: "",
      endMonth: "",
      endYear: "",
    };
    setList((prev) => [newItem, ...prev]);
  };

  /**
   * Remove an education item by id.
   *
   * @param {string|number} id
   */
  const handleDelete = (id) => {
    setList((prev) => prev.filter((item) => item.id !== id));
  };

  const validate = () => {
    const newErrors = {};
    list.forEach((item) => {
      if (!item.institution?.trim())
        newErrors[`${item.id}-institution`] = "School is required";
      if (!item.degree?.trim())
        newErrors[`${item.id}-degree`] = "Degree is required";
      if (!item.field?.trim())
        newErrors[`${item.id}-field`] = "Field of study is required";

      if (!item.startMonth || !item.startYear) {
        newErrors[`${item.id}-startDate`] = "Start date is required";
      }

      if (!item.endMonth || !item.endYear) {
        newErrors[`${item.id}-endDate`] = "End date is required";
      } else {
        const startScore = getDateScore(item.startYear, item.startMonth);
        const endScore = getDateScore(item.endYear, item.endMonth);
        if (endScore < startScore) {
          newErrors[`${item.id}-endDate`] =
            "End date cannot be earlier than start date";
        }
      }
    });
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  /**
   * Submit form after validation.
   */
  const handleSubmit = async () => {
    if (!validate()) return;
    setIsSaving(true);
    try {
      const payload = {
        education: list.map((item) => ({
          ...(String(item.id).startsWith("new-") ? {} : { id: item.id }),
          school: item.institution,
          degree: item.degree,
          fieldOfStudy: item.field,
          startDate: formatDateFromParts(item.startMonth, item.startYear),
          endDate: formatDateFromParts(item.endMonth, item.endYear),
        })),
      };
      await onSave(payload);
      onClose();
    } catch (e) {
      console.error("Save failed", e);
    } finally {
      setIsSaving(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="modal-overlay">
      <div className="modal-content">
        <div className="section-header">
          <h3>Edit Education</h3>
          <Button size="sm" onClick={handleAdd}>
            +
          </Button>
        </div>

        <div className="scrollable-form-area">
          {list.map((item) => (
            <EducationFormItem
              key={item.id}
              item={item}
              errors={errors}
              onChange={handleChange}
              onDelete={handleDelete}
            />
          ))}
        </div>

        <div className="modal-actions">
          <Button variant="outline" onClick={onClose} disabled={isSaving}>
            Cancel
          </Button>
          <Button onClick={handleSubmit} disabled={isSaving}>
            {isSaving ? "Saving..." : "Save"}
          </Button>
        </div>
      </div>
    </div>
  );
};

export default EducationEditModal;
