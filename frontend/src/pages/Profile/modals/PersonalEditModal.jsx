import React, { useState, useEffect } from "react";
import TimezoneSelector from "@/components/common/TimezoneSelector";
import { Button } from "@/components/ui/button";

const LABEL = "mb-2 block text-sm font-semibold text-foreground";
const FIELD =
  "w-full rounded-[10px] border-2 bg-background px-4 py-3 text-[0.9375rem] text-foreground transition-all focus:border-primary focus:shadow-sm focus:outline-none";
const ERROR_TEXT = "mt-1 block text-xs text-destructive";

/**
 * PersonalEditModal allows editing personal profile information including
 * name, timezone, and LinkedIn. Email addresses are not editable here — they
 * are managed on the Sign in & security settings page.
 *
 * @param {boolean} isOpen - Controls modal visibility
 * @param {function} onClose - Callback to close the modal
 * @param {object} initialData - Initial form data
 * @param {function} onSave - Callback for saving data
 * @param {boolean} canEditTimezone - Whether the user can edit timezone
 * @param {string} nextEditableDate - Next allowed timezone update date
 */
const PersonalEditModal = ({
  isOpen,
  onClose,
  initialData,
  onSave,
  canEditTimezone,
  nextEditableDate,
}) => {
  const [formData, setFormData] = useState({});
  const [errors, setErrors] = useState({});
  const [isSaving, setIsSaving] = useState(false);

  // Initialize form state when modal opens
  useEffect(() => {
    if (isOpen && initialData) {
      setFormData(structuredClone(initialData));
      setErrors({});
      setIsSaving(false);
    }
  }, [isOpen, initialData]);

  if (!isOpen) return null;

  /** Handle changes for regular input fields */
  const handleChange = (name, value) => {
    setFormData((prev) => ({ ...prev, [name]: value }));
    setErrors((prev) => {
      const next = { ...prev };
      delete next[name];
      return next;
    });
  };

  /** Validate the entire form */
  const validate = () => {
    const newErrors = {};

    // Required field validation
    if (!formData.firstName?.trim())
      newErrors.firstName = "First name is required";
    if (!formData.lastName?.trim())
      newErrors.lastName = "Last name is required";
    if (!formData.timezone) newErrors.timezone = "Timezone is required";

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  /** Submit form data */
  const handleSubmit = async () => {
    if (!validate()) return;

    setIsSaving(true);
    try {
      // Email is managed in Settings (via sign-in methods), not here.
      const payload = {
        user: {
          firstName: formData.firstName,
          lastName: formData.lastName,
          preferredName: formData.preferredName,
          timezone: formData.timezone,
          linkedinLink: formData.linkedin,
          communicationMethod: formData.communicationMethod,
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
    <div className="fixed inset-0 z-[1000] flex h-full w-full items-center justify-center bg-black/40 backdrop-blur-[4px] animate-in fade-in duration-200">
      <div className="max-h-[90vh] w-[90%] max-w-[700px] overflow-y-auto rounded-2xl border bg-background p-10 animate-in slide-in-from-bottom-4 duration-300">
        <div className="mb-5 flex items-center justify-between">
          <h3 className="text-xl font-semibold">Edit Personal Information</h3>
        </div>

        <div>
          {/* First Name */}
          <div className="mb-5">
            <label className={LABEL}>
              First Name <span className="ml-1 text-destructive">*</span>
            </label>
            <input
              type="text"
              className={`${FIELD}${errors.firstName ? " border-destructive" : ""}`}
              value={formData.firstName || ""}
              onChange={(e) => handleChange("firstName", e.target.value)}
            />
            {errors.firstName && (
              <span className={ERROR_TEXT}>{errors.firstName}</span>
            )}
          </div>

          {/* Last Name */}
          <div className="mb-5">
            <label className={LABEL}>
              Last Name <span className="ml-1 text-destructive">*</span>
            </label>
            <input
              type="text"
              className={`${FIELD}${errors.lastName ? " border-destructive" : ""}`}
              value={formData.lastName || ""}
              onChange={(e) => handleChange("lastName", e.target.value)}
            />
            {errors.lastName && (
              <span className={ERROR_TEXT}>{errors.lastName}</span>
            )}
          </div>

          {/* Preferred Name */}
          <div className="mb-5">
            <label className={LABEL}>Preferred Name</label>
            <input
              type="text"
              className={FIELD}
              value={formData.preferredName || ""}
              onChange={(e) => handleChange("preferredName", e.target.value)}
            />
          </div>

          {/* Timezone */}
          <div className="mb-5">
            <label className={LABEL}>
              Current Timezone <span className="ml-1 text-destructive">*</span>
            </label>
            <TimezoneSelector
              value={formData.timezone || ""}
              onChange={(opt) => handleChange("timezone", opt?.value ?? "")}
              isDisabled={!canEditTimezone}
            />
            {errors.timezone && (
              <span className={ERROR_TEXT}>{errors.timezone}</span>
            )}
            <span className="text-xs">
              Timezone can only be updated once every 30 days.
              <br />
              {!canEditTimezone && `Next editable date: ${nextEditableDate}.`}
            </span>
          </div>

          {/* LinkedIn */}
          <div className="mb-5">
            <label className={LABEL}>LinkedIn</label>
            <input
              type="text"
              className={FIELD}
              value={formData.linkedin || ""}
              onChange={(e) => handleChange("linkedin", e.target.value)}
            />
          </div>
        </div>

        {/* Modal Actions */}
        <div className="mt-10 flex justify-end gap-3 border-t-2 pt-6">
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

export default PersonalEditModal;
