import React, { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import "@/pages/Profile/modals/Modal.css";
import {
  months,
  formatDateFromParts,
  getDateScore,
} from "@/pages/Profile/utils";
import EducationFormItem from "@/pages/Profile/components/EducationFormItem";

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
    const now = new Date();
    const currentScore = getDateScore(
      now.getFullYear(),
      months[now.getMonth()],
    );
    list.forEach((item) => {
      const startScore = getDateScore(item.startYear, item.startMonth);
      if (!item.institution?.trim())
        newErrors[`${item.id}-institution`] = "School is required";
      if (!item.degree?.trim())
        newErrors[`${item.id}-degree`] = "Degree is required";
      if (!item.field?.trim())
        newErrors[`${item.id}-field`] = "Field of study is required";

      if (!item.startMonth || !item.startYear) {
        newErrors[`${item.id}-startDate`] = "Start date is required";
      } else {
        if (startScore > currentScore) {
          newErrors[`${item.id}-startDate`] =
            "Start date cannot be in the future";
        }
      }

      if (!item.endMonth || !item.endYear) {
        newErrors[`${item.id}-endDate`] = "End date is required";
      } else {
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
