import React, { useState, useEffect } from "react";
import { toast } from "sonner";
import {
  months,
  formatDateFromParts,
  getDateScore,
} from "@/pages/Profile/utils";
import { Button } from "@/components/ui/button";
import ExperienceFormItem from "@/pages/Profile/components/ExperienceFormItem";

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
    const now = new Date();
    const currentScore = getDateScore(
      now.getFullYear(),
      months[now.getMonth()],
    );

    list.forEach((item) => {
      const startScore = getDateScore(item.startYear, item.startMonth);
      if (!item.title?.trim())
        newErrors[`${item.id}-title`] = "Title is required";
      if (!item.company?.trim())
        newErrors[`${item.id}-company`] = "Company is required";
      if (!item.startMonth || !item.startYear) {
        newErrors[`${item.id}-startDate`] = "Start date is required";
      } else {
        if (startScore > currentScore) {
          newErrors[`${item.id}-startDate`] =
            "Start date cannot be in the future";
        }
      }
      if (!item.isCurrentlyWorking) {
        if (!item.endMonth || !item.endYear) {
          newErrors[`${item.id}-endDate`] = "End date is required";
        } else {
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
      };
      await onSave(payload);
      onClose();
    } catch (e) {
      console.error("Save failed", e);
      toast.error("Couldn't save your changes. Please try again.");
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-[1000] flex h-full w-full items-center justify-center bg-black/40 backdrop-blur-[4px] animate-in fade-in duration-200">
      <div className="max-h-[90vh] w-[90%] max-w-[700px] overflow-y-auto rounded-2xl border bg-background p-10 animate-in slide-in-from-bottom-4 duration-300">
        <div className="mb-5 flex items-center justify-between">
          <h3 className="text-xl font-semibold">Edit Experience</h3>
          <Button size="sm" onClick={handleAdd}>
            +
          </Button>
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

        <div className="mt-10 flex justify-end gap-3 border-t-2 pt-6">
          <Button variant="outline" onClick={onClose} disabled={isSaving}>
            Cancel
          </Button>
          <Button
            onClick={handleSubmit}
            disabled={isSaving}
            className="save-btn"
          >
            {isSaving ? "Saving..." : "Save"}
          </Button>
        </div>
      </div>
    </div>
  );
};

export default ExperienceEditModal;
