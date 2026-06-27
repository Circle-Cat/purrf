import React, { useState, useEffect } from "react";
import "@/pages/Profile/modals/Modal.css";
import TimezoneSelector from "@/components/common/TimezoneSelector";
import { Button } from "@/components/ui/button";

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
    <div className="modal-overlay">
      <div className="modal-content">
        <div className="mb-5 flex items-center justify-between">
          <h3>Edit Personal Information</h3>
        </div>

        <div className="scrollable-form-area">
          {/* First Name */}
          <div className="form-group">
            <label>
              First Name <span className="required">*</span>
            </label>
            <input
              type="text"
              className={errors.firstName ? "input-error" : ""}
              value={formData.firstName || ""}
              onChange={(e) => handleChange("firstName", e.target.value)}
            />
            {errors.firstName && (
              <span className="error-text">{errors.firstName}</span>
            )}
          </div>

          {/* Last Name */}
          <div className="form-group">
            <label>
              Last Name <span className="required">*</span>
            </label>
            <input
              type="text"
              className={errors.lastName ? "input-error" : ""}
              value={formData.lastName || ""}
              onChange={(e) => handleChange("lastName", e.target.value)}
            />
            {errors.lastName && (
              <span className="error-text">{errors.lastName}</span>
            )}
          </div>

          {/* Preferred Name */}
          <div className="form-group">
            <label>Preferred Name</label>
            <input
              type="text"
              value={formData.preferredName || ""}
              onChange={(e) => handleChange("preferredName", e.target.value)}
            />
          </div>

          {/* Timezone */}
          <div className="form-group">
            <label>
              Current Timezone <span className="required">*</span>
            </label>
            <TimezoneSelector
              value={formData.timezone || ""}
              onChange={(opt) => handleChange("timezone", opt?.value ?? "")}
              isDisabled={!canEditTimezone}
            />
            {errors.timezone && (
              <span className="error-text">{errors.timezone}</span>
            )}
            <span className="timezone-info-text">
              Timezone can only be updated once every 30 days.
              <br />
              {!canEditTimezone && `Next editable date: ${nextEditableDate}.`}
            </span>
          </div>

          {/* LinkedIn */}
          <div className="form-group">
            <label>LinkedIn</label>
            <input
              type="text"
              value={formData.linkedin || ""}
              onChange={(e) => handleChange("linkedin", e.target.value)}
            />
          </div>
        </div>

        {/* Modal Actions */}
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

export default PersonalEditModal;
