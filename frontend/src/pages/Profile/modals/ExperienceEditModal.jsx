import React, { useState, useEffect } from "react";
import "@/pages/Profile/modals/Modal.css";
import {
  months,
  years,
  formatDateFromParts,
  getDateScore,
} from "@/pages/Profile/utils";

/**
 * Form item for editing a single experience entry.
 *
 * @param {Object} props
 * @param {Object} props.item - Experience data.
 * @param {Object<string, string>} props.errors - Validation errors keyed by `${id}-${field}`.
 * @param {(id: string|number, field: string, value: any) => void} props.onChange - Change handler.
 * @param {(id: string|number) => void} props.onDelete - Delete handler.
 */
const ExperienceFormItem = ({ item, errors, onChange, onDelete }) => {
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

      <button
        type="button"
        className="delete-btn"
        onClick={() => onDelete(item.id)}
      >
        -
      </button>
    </div>
  );
};

/**
 * Modal for editing the experience list.
 *
 * @param {Object} props
 * @param {boolean} props.isOpen - Whether the modal is open.
 * @param {() => void} props.onClose - Close handler.
 * @param {Array<Object>} props.initialData - Initial experience data.
 * @param {(payload: any) => Promise<void>} props.onSave - Save handler.
 */
const ExperienceEditModal = ({ isOpen, onClose, initialData, onSave }) => {
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
   * Handle field change for an experience item and clear related errors.
   *
   * @param {string|number} id - Item id.
   * @param {string} field - Field name.
   * @param {*} value - New value.
   */
  const handleChange = (id, field, value) => {
    setList((prev) =>
      prev.map((item) => {
        const isTarget = item.id === id;

        // If set to currently working, clear end date fields
        if (field === "isCurrentlyWorking" && value === true) {
          if (isTarget) {
            return {
              ...item,
              isCurrentlyWorking: true,
              endMonth: "",
              endYear: "",
            };
          }
          return { ...item, isCurrentlyWorking: false };
        }

        return isTarget ? { ...item, [field]: value } : item;
      }),
    );

    // Clear related validation errors automatically
    setErrors((prev) => {
      const next = { ...prev };
      delete next[`${id}-${field}`];
      if (field === "startMonth" || field === "startYear") {
        delete next[`${id}-startDate`];
      }
      if (
        field === "endMonth" ||
        field === "endYear" ||
        field === "isCurrentlyWorking"
      ) {
        delete next[`${id}-endDate`];
      }
      return next;
    });
  };

  /**
   * Add a new empty experience item.
   */
  const handleAdd = () => {
    const newItem = {
      id: `new-${Date.now()}`,
      title: "",
      company: "",
      startMonth: "",
      startYear: "",
      endMonth: "",
      endYear: "",
      isCurrentlyWorking: false,
    };
    setList((prev) => [newItem, ...prev]);
  };

  /**
   * Remove an experience item by id.
   *
   * @param {string|number} id
   */
  const handleDelete = (id) => {
    setList((prev) => prev.filter((item) => item.id !== id));
  };

  /**
   * Validate all experience items.
   *
   * @returns {boolean} True if valid.
   */
  const validate = () => {
    const newErrors = {};
    list.forEach((item) => {
      if (!item.title?.trim())
        newErrors[`${item.id}-title`] = "Title is required";
      if (!item.company?.trim())
        newErrors[`${item.id}-company`] = "Company is required";
      if (!item.startMonth || !item.startYear) {
        newErrors[`${item.id}-startDate`] = "Start date is required";
      }

      if (!item.isCurrentlyWorking) {
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
        profile: {
          workHistory: list.map((item) => ({
            ...(String(item.id).startsWith("new-") ? {} : { id: item.id }),
            title: item.title,
            companyOrOrganization: item.company,
            isCurrentJob: item.isCurrentlyWorking,
            startDate: formatDateFromParts(item.startMonth, item.startYear),
            endDate: item.isCurrentlyWorking
              ? null
              : formatDateFromParts(item.endMonth, item.endYear),
          })),
        },
      };
      await onSave(payload);
      onClose();
    } catch (e) {
      console.error("Save failed", e);
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="modal-overlay">
      <div className="modal-content">
        <div className="section-header">
          <h3>Edit Experience</h3>
          <button className="edit-button" onClick={handleAdd}>
            +
          </button>
        </div>

        <div className="scrollable-form-area">
          {list.map((item) => (
            <ExperienceFormItem
              key={item.id}
              item={item}
              errors={errors}
              onChange={handleChange}
              onDelete={handleDelete}
            />
          ))}
        </div>

        <div className="modal-actions">
          <button type="button" onClick={onClose} disabled={isSaving}>
            Cancel
          </button>
          <button
            type="button"
            onClick={handleSubmit}
            disabled={isSaving}
            className="save-btn"
          >
            {isSaving ? "Saving..." : "Save"}
          </button>
        </div>
      </div>
    </div>
  );
};

export default ExperienceEditModal;
